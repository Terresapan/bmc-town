# Memory Evaluation Strategy

This document outlines the strategy for evaluating the "Shared Living Context" (Fact Checker) feature.

## Goal
To verify that the `MemoryService` correctly extracts business facts from conversations and resolves conflicts without hallucinations.

## Architecture

We use a **two-phase evaluation approach**:
1. **Offline Dataset Testing** - Deterministic tests against labeled examples
2. **Online LLM Judge** - Runtime evaluation of production runs via LangSmith

---

## Phase 1: Offline Dataset Testing (Recommended for Development)

### Test Dataset
Location: `bmc-api/data/memory_test_cases.json`

Each test case contains:
- `existing_memory`: The starting state
- `conversation`: The input conversation
- `expected_output`: The correct extraction result
- `expected_facts`: List of atomic facts for metric calculation

### Metric Formulas

For each test case, we compute:

```
True Positives (TP) = Facts correctly extracted (in both expected and actual)
False Positives (FP) = Hallucinated facts (in actual but NOT in expected)
False Negatives (FN) = Missed facts (in expected but NOT in actual)

Precision = TP / (TP + FP)   # "Of what was extracted, how much was correct?"
Recall = TP / (TP + FN)      # "Of what should have been extracted, how much was found?"
F1 = 2 * (Precision * Recall) / (Precision + Recall)  # Harmonic mean
```

### Running Offline Tests

```bash
cd bmc-api
python -m pytest evals/test_memory_extraction.py -v
```

---

## Phase 2: Online LLM Judge (For Production Monitoring)

### Target Runs
The evaluator targets LangSmith runs with tag: `memory_extraction`.

### Evaluation Process

Instead of asking the LLM for a subjective score, we use it for **fact enumeration**:

1. **Extract Ground Truth Facts**: Ask LLM to list all business facts from the conversation
2. **Extract Output Facts**: Parse the extractor's output into atomic facts
3. **Compute Overlap**: Calculate Precision/Recall/F1 programmatically

### Judge Prompt (Fact Enumeration)

```
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
Format each fact as: "category: fact_content"

Example:
- "customer_segments: Small business owners"
- "constraint: No subscription model"

### Step 2: List Extracted Facts  
List ALL facts present in the EXTRACTED OUTPUT that are NEW (not in EXISTING MEMORY).

### Step 3: Identify Issues
- **Missed Facts**: Facts from Step 1 that are NOT in Step 2
- **Hallucinations**: Facts in Step 2 that are NOT in Step 1

Output as JSON:
{
  "conversation_facts": ["fact1", "fact2"],
  "extracted_facts": ["fact1", "fact3"],
  "missed_facts": ["fact2"],
  "hallucinated_facts": ["fact3"]
}
```

### Scoring

After receiving the JSON, compute:
```python
tp = len(extracted_facts) - len(hallucinated_facts)
fp = len(hallucinated_facts)
fn = len(missed_facts)

precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
```

---

## Evaluation Metrics Summary

| Metric | Description | Target |
|--------|-------------|--------|
| **Precision** | Avoids hallucinations | > 0.95 |
| **Recall** | Captures all stated facts | > 0.85 |
| **F1 Score** | Balanced performance | > 0.90 |
| **Conflict Resolution** | Correctly handles "Actually..." statements | 100% |
| **Minimalism** | Returns unchanged memory for chit-chat | 100% |

---

## Implementation Files

| File | Purpose |
|------|---------|
| `data/memory_test_cases.json` | Labeled test dataset (10 cases) |
| `evals/memory_evaluator.py` | LLM Judge evaluator class |
| `evals/test_memory_extraction.py` | Pytest-based offline tests |

---

## Test Case Coverage

| ID | Scenario | Tests |
|----|----------|-------|
| test_001 | Simple extraction | Basic fact capture |
| test_002 | No extraction | Chit-chat handling |
| test_003 | Constraint extraction | Rejection → constraint |
| test_004 | Conflict resolution | User changes mind |
| test_005 | Multiple blocks | Cross-block extraction |
| test_006 | Non-agreement | "Maybe" handling |
| test_007 | Preference extraction | User style preferences |
| test_008 | Append behavior | "I also want..." |
| test_009 | Cost and revenue | Financial facts |
| test_010 | Explicit agreement | Expert suggestion + user confirms |
