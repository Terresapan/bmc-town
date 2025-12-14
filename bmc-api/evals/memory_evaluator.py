"""
Memory Accuracy Evaluator

Uses an LLM Judge (Gemini) to enumerate facts from conversations and extracted outputs,
then computes Precision, Recall, and F1 scores programmatically.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from langsmith.schemas import Run
from langsmith.evaluation import RunEvaluator, EvaluationResult

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Judge prompt for fact enumeration
_JUDGE_PROMPT = """
You are a Fact Extraction Auditor.

## Input 1: CONVERSATION
{conversation_text}

## Input 2: EXISTING MEMORY
{existing_memory}

## Input 3: EXTRACTED OUTPUT
{extracted_output}

---

## Your Task

### Step 1: List Conversation Facts
List ALL business facts that the USER explicitly stated or agreed to in the conversation.
Only include facts where the user made a clear statement or gave explicit confirmation.
Do NOT include expert suggestions that the user didn't confirm.

Format each fact as: "category: fact_content"
Categories: customer_segments, value_propositions, channels, customer_relationships, 
revenue_streams, key_resources, key_activities, key_partnerships, cost_structure, 
constraint, preference, pending_topic

### Step 2: List Extracted Facts  
List ALL facts present in the EXTRACTED OUTPUT that are NEW (not already in EXISTING MEMORY).
Use the same format: "category: fact_content"

### Step 3: Identify Issues
- **Missed Facts**: Facts from Step 1 that are NOT captured in Step 2
- **Hallucinations**: Facts in Step 2 that are NOT supported by the conversation in Step 1

Output as JSON only, no markdown:
{{
  "conversation_facts": ["fact1", "fact2"],
  "extracted_facts": ["fact1", "fact3"],
  "missed_facts": ["fact2"],
  "hallucinated_facts": ["fact3"],
  "reasoning": "Brief explanation of your analysis"
}}
"""


@dataclass
class MemoryEvalResult:
    """Result of memory extraction evaluation."""
    precision: float
    recall: float
    f1: float
    conversation_facts: List[str]
    extracted_facts: List[str]
    missed_facts: List[str]
    hallucinated_facts: List[str]
    reasoning: str


class MemoryAccuracyEvaluator(RunEvaluator):
    """
    Evaluates memory extraction runs using an LLM judge.
    
    Instead of asking the LLM for a subjective score, we:
    1. Ask it to enumerate facts from the conversation
    2. Ask it to enumerate facts from the extraction output
    3. Compute Precision/Recall/F1 programmatically
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Gemini API key."""
        import os
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
        else:
            logger.warning("No GEMINI_API_KEY found. Evaluator will fail on evaluate_run.")
            self.model = None
    
    def _compute_metrics(self, judge_response: Dict) -> MemoryEvalResult:
        """Compute Precision, Recall, F1 from judge response."""
        conversation_facts = judge_response.get("conversation_facts", [])
        extracted_facts = judge_response.get("extracted_facts", [])
        missed_facts = judge_response.get("missed_facts", [])
        hallucinated_facts = judge_response.get("hallucinated_facts", [])
        reasoning = judge_response.get("reasoning", "")
        
        # Calculate TP, FP, FN
        tp = len(extracted_facts) - len(hallucinated_facts)
        tp = max(0, tp)  # Ensure non-negative
        fp = len(hallucinated_facts)
        fn = len(missed_facts)
        
        # Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return MemoryEvalResult(
            precision=precision,
            recall=recall,
            f1=f1,
            conversation_facts=conversation_facts,
            extracted_facts=extracted_facts,
            missed_facts=missed_facts,
            hallucinated_facts=hallucinated_facts,
            reasoning=reasoning
        )
    
    def evaluate_run(
        self, 
        run: Run, 
        example: Optional[Any] = None
    ) -> EvaluationResult:
        """
        Evaluate a memory extraction run.
        
        Args:
            run: The LangSmith run to evaluate
            example: Optional reference example (not used in online evaluation)
            
        Returns:
            EvaluationResult with F1 score and detailed comment
        """
        if not self.model:
            return EvaluationResult(
                key="memory_accuracy",
                score=None,
                comment="Evaluator not configured (missing API key)"
            )
        
        try:
            # Extract inputs from run
            inputs = run.inputs or {}
            outputs = run.outputs or {}
            
            # Get conversation and memory data
            # The prompt format uses these placeholders
            conversation_text = inputs.get("conversation_text", "")
            existing_memory = inputs.get("existing_memory", "{}")
            
            # If not in expected format, try to extract from the prompt itself
            if not conversation_text:
                # The run might have the full prompt as input
                prompt_input = str(inputs)
                if "RECENT CONVERSATION" in prompt_input:
                    # Try to parse it
                    pass  # Complex parsing, skip for now
            
            # Get extracted output
            extracted_output = outputs.get("output", outputs.get("content", str(outputs)))
            
            if not conversation_text:
                return EvaluationResult(
                    key="memory_accuracy",
                    score=None,
                    comment="Could not extract conversation from run inputs"
                )
            
            # Construct judge prompt
            prompt = _JUDGE_PROMPT.format(
                conversation_text=conversation_text,
                existing_memory=existing_memory,
                extracted_output=extracted_output
            )
            
            # Call Gemini
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse JSON response
            # Clean up potential markdown formatting
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()
            
            judge_response = json.loads(response_text)
            
            # Compute metrics
            result = self._compute_metrics(judge_response)
            
            # Build comment
            comment = (
                f"Precision: {result.precision:.2f}, "
                f"Recall: {result.recall:.2f}, "
                f"F1: {result.f1:.2f}. "
            )
            
            if result.missed_facts:
                comment += f"Missed: {result.missed_facts}. "
            if result.hallucinated_facts:
                comment += f"Hallucinated: {result.hallucinated_facts}. "
            if not result.missed_facts and not result.hallucinated_facts:
                comment += "Perfect extraction!"
            
            return EvaluationResult(
                key="memory_accuracy",
                score=result.f1,  # Use F1 as the primary score
                comment=comment
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse judge response: {e}")
            return EvaluationResult(
                key="memory_accuracy",
                score=None,
                comment=f"Judge response parsing failed: {e}"
            )
        except Exception as e:
            logger.error(f"Memory evaluation failed: {e}")
            return EvaluationResult(
                key="memory_accuracy",
                score=None,
                comment=f"Evaluation error: {e}"
            )


def evaluate_test_case(
    test_case: Dict,
    memory_service_output: Dict,
    api_key: Optional[str] = None
) -> MemoryEvalResult:
    """
    Evaluate a single test case from memory_test_cases.json.
    
    This is a helper function for offline testing.
    
    Args:
        test_case: Test case dict with conversation, existing_memory, expected_output
        memory_service_output: The actual output from MemoryService
        api_key: Gemini API key
        
    Returns:
        MemoryEvalResult with metrics
    """
    import os
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    prompt = _JUDGE_PROMPT.format(
        conversation_text=test_case["conversation"],
        existing_memory=json.dumps(test_case["existing_memory"]),
        extracted_output=json.dumps(memory_service_output)
    )
    
    response = model.generate_content(prompt)
    response_text = response.text.strip()
    
    # Clean up markdown
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    response_text = response_text.strip()
    
    judge_response = json.loads(response_text)
    
    evaluator = MemoryAccuracyEvaluator()
    return evaluator._compute_metrics(judge_response)
