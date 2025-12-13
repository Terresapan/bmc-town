import os
import sys
import json
import base64
import time
import tempfile
import logging
from pathlib import Path
import filetype

# --- 1. SETUP PATHS & CONFIG ---
# Add the current directory's parent to sys.path so we can import 'philoagents.config'
# correctly, even when running this script directly from /tests/
current_dir = Path(__file__).resolve().parent
# In docker container: /app/tests/ -> add /app to path
# In local dev: /app/philoagents-api/tests/ -> add /app/philoagents-api to path
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

# Suppress logging from httpx and google_genai
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

try:
    from bmc.config import settings
    # print(f"🔧 [Judge] Loaded Config: Model={settings.GEMINI_LLM_MODEL_EVALUATION}")
except ImportError as e:
    print(f"❌ [Judge] Failed to import settings: {e}")
    print("   Ensure you are running with 'uv run python tests/llm_judge_gemini.py' from project root")
    sys.exit(1)

# --- 2. IMPORT GOOGLE & LANGSMITH SDK ---
from google import genai
from langsmith import Client
from langsmith.evaluation import RunEvaluator, EvaluationResult

class ContentAccuracyEvaluator(RunEvaluator):
    def __init__(self):
        # Use settings from config.py
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_LLM_MODEL_EVALUATION
        
        # Configure the SDK
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing in settings!")
        
        self.client = genai.Client(api_key=self.api_key)

    def _upload_to_gemini(self, base64_data, mime_type, suffix):
        """Helper: Decodes base64, saves to temp, uploads to Google File API."""
        try:
            # 1. Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                file_content = base64.b64decode(base64_data)
                tmp.write(file_content)
                tmp_path = tmp.name

            # print(f"  [Judge] Uploading {len(file_content)} bytes to Gemini File API...")
            
            # 2. Upload to Google
            file_ref = self.client.files.upload(file=tmp_path, config={'mime_type': mime_type})
            
            # 3. Wait for processing (Critical for PDFs/Videos)
            while file_ref.state.name == "PROCESSING":
                # print("  [Judge] Google is processing the file...", end="\r")
                time.sleep(1)
                file_ref = self.client.files.get(name=file_ref.name)
                
            if file_ref.state.name == "FAILED":
                raise ValueError(f"File processing failed on Google side: {file_ref.state.name}")
                
            # print(f"  [Judge] File Ready: {file_ref.display_name} ({file_ref.uri})")
            
            # 4. Cleanup local temp file
            os.remove(tmp_path)
            
            return file_ref

        except Exception as e:
            # print(f"  [Judge] Upload Error: {e}")
            return None

    def evaluate_run(self, run, example=None) -> EvaluationResult:
        inputs = run.inputs or {}
        outputs = run.outputs or {}
        
        # --- 1. FILTER: Only Judge Runs with Files ---
        has_pdf = bool(inputs.get("pdf_base64"))
        has_image = bool(inputs.get("image_base64"))
        
        if not (has_pdf or has_image):
            return None 

        # --- 2. EXTRACT CONTEXT ---
        # (Same extraction logic as before)
        user_query = "Unknown query"
        if "messages" in inputs:
            for msg in reversed(inputs["messages"]):
                msg_type = getattr(msg, 'type', None) or msg.get('type')
                if msg_type == "human":
                    content = getattr(msg, 'content', None) or msg.get('content')
                    if isinstance(content, list):
                        for part in content:
                            if part.get("type") == "text":
                                user_query = part.get("text")
                    elif isinstance(content, str):
                        user_query = content
                    break
        
        model_answer = "No response"
        try:
            msgs = outputs.get("messages", [])
            if msgs:
                last_msg = msgs[-1]
                model_answer = getattr(last_msg, 'content', None) or last_msg.get('content')
        except Exception:
            pass

        # --- 3. PREPARE FILES (MULTI-FILE SUPPORT) ---
        file_refs = []
        
        # Check PDF
        if has_pdf:
            # print("  [Judge] Found PDF. Uploading...")
            pdf_ref = self._upload_to_gemini(
                inputs['pdf_base64'], 
                mime_type="application/pdf", 
                suffix=".pdf"
            )
            if pdf_ref:
                file_refs.append(pdf_ref)

        # Check Image (Now using IF, not ELIF)
        if has_image:
            # print("  [Judge] Found Image. Uploading...")
            image_base64 = inputs['image_base64']
            mime_type = "image/png"
            suffix = ".png"
            
            try:
                image_bytes = base64.b64decode(image_base64)
                kind = filetype.guess(image_bytes)
                if kind:
                    mime_type = kind.mime
                    suffix = "." + kind.extension
            except Exception:
                pass

            img_ref = self._upload_to_gemini(
                image_base64, 
                mime_type=mime_type, 
                suffix=suffix
            )
            if img_ref:
                file_refs.append(img_ref)

        if not file_refs:
            return EvaluationResult(key="accuracy_error", comment="Failed to upload file to Gemini")

        # --- 4. CONSTRUCT PROMPT ---
        # We start with the list of file references
        prompt_parts = file_refs + [
            f"""
            You are a QA Auditor evaluating an AI Assistant.
            
            TASK: Check if the AI's response is factually supported by the ATTACHED FILE(S).
            
            CONTEXT:
            User Query: "{user_query}"
            AI Response: "{model_answer}"
            
            INSTRUCTIONS:
            Step 1: Determine Relevance
            - Does the User Query ask for information, summary, or analysis of the ATTACHED FILE(S)?
            - Or is it a general question, chitchat, or unrelated to the specific file content?

            Step 2: Evaluate
            - CASE A: Query is UNRELATED to the file.
              -> Result: N/A (Score null).
              -> Reasoning: State that the query is unrelated to the file content.

            - CASE B: Query is RELATED to the file.
              -> Check: Does the AI's answer strictly align with the visible content in the file?
              -> Hallucination Check: If the AI cites facts/numbers supposedly "from the file" that are not there, Score 0.
              -> Result: 1 (Supported) or 0 (Hallucination/Unsupported).
            
            Return JSON:
            {{
                "score": 1, 0, or null,
                "reasoning": "Step 1 analysis... followed by Step 2 verification..."
            }}
            """
        ]

        # --- 5. GENERATE JUDGMENT ---
        try:
            # Retry loop for rate limits
            for attempt in range(3):
                try:
                    # Generate content (no retry needed for Flash model)
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt_parts,
                        config={"response_mime_type": "application/json"}
                    )
                    break # Success
                except Exception as api_error:
                    if "429" in str(api_error) and attempt < 2:
                        print(f"  [Judge] ⏳ Rate limit hit (429). Sleeping 15s (Attempt {attempt+1}/3)...")
                        time.sleep(15)
                        continue
                    raise api_error

            # Parse result
            result_json = json.loads(response.text)
            score = result_json.get("score") # Can be 1, 0, or None
            reasoning = result_json.get("reasoning", "No reasoning provided")

            # --- CLEANUP (Good Citizenship) ---
            # Delete the file from Google's servers to save space/privacy
            for ref in file_refs:
                try:
                    self.client.files.delete(name=ref.name)
                except:
                    pass
            
            # Determine comment icon
            icon = '⚪'
            if score == 1: icon = '✅'
            elif score == 0: icon = '❌'

            return EvaluationResult(
                key="accuracy_score",
                score=score,
                comment=f"{icon} {reasoning}",
            )

        except Exception as e:
            # Cleanup if it failed mid-flight
            for ref in file_refs:
                try:
                    self.client.files.delete(name=ref.name)
                except:
                    pass
                
            return EvaluationResult(
                key="accuracy_error",
                score=None,
                comment=f"Gemini Judge Failed: {str(e)}"
            )

# --- RUNNER ---
def test_judge_locally(project_name="Business Model Canvas", limit=1):
    client = Client()
    print(f"Fetching last {limit} runs for project '{project_name}'...")
    
    runs = client.list_runs(
        project_name=project_name,
        limit=limit,
        is_root=True
    )
    
    judge = ContentAccuracyEvaluator()
    
    for i, run in enumerate(runs):
        print(f"\n=== Run ID: {run.id} ===")
        
        # --- PROACTIVE RATE LIMITING ---
        # Sleep between runs to avoid hitting the 2 RPM limit of the Free Tier
        if i > 0:
            print("  [Judge] ⏳ Proactive sleep (15s) to respect Free Tier limits...")
            time.sleep(15)
        
        result = judge.evaluate_run(run)
        
        if result:
            print(f"FINAL SCORE: {result.score}")
            print(f"COMMENT: {result.comment}")
        else:
            print("Skipped (No file inputs)")

if __name__ == "__main__":
    test_judge_locally()