from langsmith.evaluation import RunEvaluator, EvaluationResult
import logging

# Set up logging
logger = logging.getLogger(__name__)

class RuleBasedEvaluator(RunEvaluator):
    """
    Combines fast, deterministic checks:
    1. Conciseness (<= 50 words)
    2. Identity Safety (no 'As an AI' etc.)
    3. File Integrity (if files declared, payload must exist)
    """
    def evaluate_run(self, run, example=None):
        results = []
        
        # --- EXTRACT DATA ---
        inputs = run.inputs or {}
        outputs = run.outputs
        
        # 1. Extract Output Content
        content = ""
        is_ai_message = False
        
        try:
            if not outputs:
                content = ""
            else:
                messages = outputs.get('messages')
                if not messages:
                    # Fallback: check 'output' but strictly ignore 'summary' key to avoid checking the memory summary
                    if isinstance(outputs, str):
                        content = outputs
                        is_ai_message = True # Assume string output is from AI
                    elif 'output' in outputs:
                        content = outputs['output']
                        is_ai_message = True
                else:
                    last_msg = messages[-1]
                    
                    # Determine message type
                    msg_type = "unknown"
                    if isinstance(last_msg, dict):
                        msg_type = last_msg.get('type', 'unknown')
                        content = last_msg.get('content', '') or last_msg.get('kwargs', {}).get('content', '')
                    elif hasattr(last_msg, 'type'):
                        msg_type = last_msg.type
                        content = last_msg.content
                    else:
                        # Fallback for unknown objects
                        content = str(last_msg)
                        
                    # ONLY evaluate if it's an AI message
                    if msg_type == 'ai':
                        is_ai_message = True
                    else:
                        logger.info(f"Skipping evaluation: Last message type is '{msg_type}', not 'ai'")

        except Exception as e:
            logger.warning(f"Error parsing run outputs: {e}")
            content = ""

        # If we couldn't find an AI message, return a skipped result for content checks
        if not is_ai_message:
            return [{
                "key": "eval_skipped",
                "score": None,
                "comment": "Skipped: Output was not an AI message"
            }]

        # --- CHECK 1: CONCISENESS & WORD COUNT ---
        word_count = len(content.split())
        is_concise = 1 if word_count <= 50 else 0
        
        results.append({
            "key": "is_concise",
            "score": is_concise,
            "comment": "Pass" if is_concise else f"Fail: {word_count} words > 50"
        })
        results.append({
            "key": "word_count",
            "score": word_count, # Using score field for numeric value as well, or we can use 'value'
            # "value": word_count, # Explicit value field for clarity
            "comment": f"{word_count} words"
        })

        # --- CHECK 2: SAFETY ---
        content_lower = content.lower()
        forbidden_phrases = [
            "as an ai", 
            "language model", 
            "virtual assistant", 
            "artificial intelligence",
            "i am a bot"
        ]
        violation = any(phrase in content_lower for phrase in forbidden_phrases)
        is_safe = 0 if violation else 1
        
        results.append({
            "key": "is_safe",
            "score": is_safe,
            "comment": "Pass" if is_safe else "Fail: Identity violation detected"
        })

        # --- CHECK 3: FILE INTEGRITY (Conditional) ---
        pdf_name_signal = inputs.get("pdf_name")
        image_name_signal = inputs.get("image_name") 
        has_pdf_payload = bool(inputs.get("pdf_base64"))
        has_image_payload = bool(inputs.get("image_base64"))

        # Only evaluate if files are involved
        if pdf_name_signal or image_name_signal or has_pdf_payload or has_image_payload:
            errors = []
            files_verified = []

            # Check PDF
            if pdf_name_signal:
                if has_pdf_payload:
                    files_verified.append("PDF")
                else:
                    errors.append(f"Missing PDF payload for '{pdf_name_signal}'")
            elif has_pdf_payload:
                files_verified.append("PDF (Unnamed)")

            # Check Image
            if image_name_signal:
                if has_image_payload:
                    files_verified.append("Image")
                else:
                    errors.append(f"Missing Image payload for '{image_name_signal}'")
            elif has_image_payload:
                files_verified.append("Image (Unnamed)")

            integrity_score = 0 if errors else 1
            comment = f"Verified: {', '.join(files_verified)}" if integrity_score else f"Errors: {'; '.join(errors)}"

            results.append({
                "key": "file_integrity",
                "score": integrity_score,
                "comment": comment
            })

        return results
