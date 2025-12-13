# Memory Evaluation Strategy

This document outlines the strategy for evaluating the "Shared Living Context" (Fact Checker) feature.

## Goal
To verify that the `MemoryService` correctly extracts business facts from conversations and resolves conflicts without hallucinations.

## Architecture

We will implement an **Online LLM Judge** that runs against LangSmith traces. This integrates with the existing `run_evals.py` infrastructure.

### 1. Target Runs
The evaluator will target runs with the tag: `memory_extraction`.
These runs represent the execution of `MemoryService.extract_business_facts`.

-   **Inputs**:
    -   `existing_memory` (JSON string)
    -   `conversation_text` (String: "User: ... \n Expert: ...")
-   **Outputs**:
    -   `BusinessInsights` (JSON structure containing `canvas_state`, `constraints`, etc.)

### 2. Evaluation Metrics

| Metric | Description | Scoring |
| :--- | :--- | :--- |
| **Recall** | Did the extractor capture all explicitly stated facts? | 0 (Missed facts) - 1 (Captured all) |
| **Precision** | Did the extractor avoid hallucinations? | 0 (Hallucinated) - 1 (Clean) |
| **Conflict Resolution** | Did it correctly overwrite old facts if the user changed their mind? | 0 (Failed) - 1 (Success) |

### 3. Implementation Plan

#### A. New Evaluator Class (`evals/memory_evaluator.py`)
Create a `MemoryAccuracyEvaluator` class inheriting from `RunEvaluator`.

-   **Logic**:
    1.  Parse the `run` inputs and outputs.
    2.  Construct a Prompt for **Gemini 2.5 Flash** (Judge Model).
    3.  **Prompt**:
        > "You are a Data Quality Auditor.
        > Read the [CONVERSATION].
        > Read the [EXTRACTED JSON].
        >
        > Check 1: Are all business facts explicitly stated in the conversation present in the JSON?
        > Check 2: Does the JSON contain any information NOT supported by the conversation (Hallucinations)?
        > Check 3: If the conversation contradicted the 'Existing Memory', was the JSON updated correctly?
        >
        > Return Score (0-1) and Reasoning."

#### B. Update Runner (`evals/run_evals.py`)
Modify the main script to include a new phase.

1.  **Phase 3: Memory Evals**
2.  Fetch runs filtered by `tags=["memory_extraction"]`.
3.  Execute `MemoryAccuracyEvaluator`.
4.  Log feedback to LangSmith with key `memory_accuracy`.

## Future Work: Offline Dataset
For regression testing, we can create a `tests/data/memory_gold_standard.json` containing pairs of conversations and expected extraction outputs, running them through `pytest`.
