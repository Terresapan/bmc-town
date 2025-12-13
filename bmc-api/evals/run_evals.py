from langsmith import Client
from rule_based_evaluator import RuleBasedEvaluator
from llm_judge_gemini import ContentAccuracyEvaluator
import time
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_batched_evals(project_name="Business Model Canvas", limit=1):
    client = Client()
    print(f"🚀 Starting Evaluation for project '{project_name}' (Last {limit} runs)")
    
    # Fetch Runs
    runs = list(client.list_runs(
        project_name=project_name,
        limit=limit,
        is_root=True
    ))
    
    print(f"📥 Fetched {len(runs)} runs.")

    # --- PHASE 1: FAST RULE-BASED CHECKS ---
    print("\n⚡ [Phase 1] Running Rule-Based Evaluators (Fast)...")
    rule_evaluator = RuleBasedEvaluator()
    
    for run in runs:
        try:
            results = rule_evaluator.evaluate_run(run)
            
            # Print results locally first
            print(f"   🔎 Run {run.id} Results:")
            for res in results:
                print(f"      - {res['key']}: {res.get('score')} ({res.get('comment')})")
                
                # Push to LangSmith
                client.create_feedback(
                    run.id,
                    key=res["key"],
                    score=res.get("score"),
                    value=res.get("value"),
                    comment=res.get("comment"),
                    source_info={"evaluator": "rule_based_v1"}
                )
            print(f"   ✅ Run {run.id} evaluated (Rules)")
        except Exception as e:
            print(f"   ❌ Run {run.id} rule eval failed: {e}")

    # --- PHASE 2: SLOW LLM CHECKS ---
    print("\n🧠 [Phase 2] Running LLM Judge (Slow)...")
    llm_evaluator = ContentAccuracyEvaluator()
    
    # Counter to track actual API calls made
    llm_calls_made = 0

    for run in runs:
        try:
            # 1. Peek at inputs to see if files exist
            inputs = run.inputs or {}
            has_files = bool(inputs.get("pdf_base64") or inputs.get("image_base64"))
            
            if not has_files:
                print(f"   ⚪ Run {run.id} skipped (No files)")
                continue

            # 2. Rate Limiting: Only sleep if we have already made at least one call
            if llm_calls_made > 0:
                print("   ⏳ Sleeping 15s to respect rate limits...")
                time.sleep(15)

            # 3. Perform Evaluation
            result = llm_evaluator.evaluate_run(run)
            llm_calls_made += 1
            
            if result:
                # Check for skipped/unrelated
                if result.score is None:
                     print(f"   ⚪ Run {run.id} Skipped (Judge): {result.comment}")
                else:
                    # Print locally regardless of pushing to LangSmith
                    print(f"   🔎 Run {run.id} Judge Result: Score={result.score} | Comment={result.comment}")

                    client.create_feedback(
                        run.id,
                        key=result.key,
                        score=result.score,
                        # value=result.value,
                        # correction=result.correction,
                        comment=result.comment,
                        source_info={"evaluator": "gemini_judge_v1"}
                    )
                    print(f"   ✅ Feedback submitted to LangSmith")
                
        except Exception as e:
            print(f"   ❌ Run {run.id} judge failed: {e}")

    print("\n🎉 Evaluation Complete!")

if __name__ == "__main__":
    run_batched_evals()
