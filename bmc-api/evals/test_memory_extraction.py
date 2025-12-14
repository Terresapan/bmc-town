"""
Offline tests for Memory Extraction feature.

Runs the MemoryService against labeled test cases and computes metrics.

Usage:
    cd bmc-api
    .venv/bin/python3 -m pytest evals/test_memory_extraction.py::TestMemoryExtraction -v -s
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bmc.application.memory_service import MemoryService
from bmc.domain.business_user import BusinessInsights
from langchain_core.messages import HumanMessage, AIMessage


# Load test cases
TEST_CASES_PATH = Path(__file__).parent.parent / "data" / "memory_test_cases.json"


def load_test_cases():
    """Load test cases from JSON file."""
    with open(TEST_CASES_PATH) as f:
        return json.load(f)


def parse_conversation(conversation_text: str):
    """Parse conversation text into message objects."""
    messages = []
    lines = conversation_text.strip().split("\n")
    
    for line in lines:
        if line.startswith("User:"):
            content = line[5:].strip()
            messages.append(HumanMessage(content=content))
        elif line.startswith("Expert:"):
            content = line[7:].strip()
            messages.append(AIMessage(content=content))
    
    return messages


def compute_fact_overlap(expected_facts: list, actual_output: dict) -> dict:
    """
    Compute simple structural overlap between expected facts and actual output.
    
    This is a simpler alternative to LLM-based evaluation for quick testing.
    """
    # Flatten actual output into fact strings
    actual_facts = []
    
    canvas_state = actual_output.get("canvas_state", {})
    for block, items in canvas_state.items():
        for item in items:
            actual_facts.append(f"{block}: {item}")
    
    for constraint in actual_output.get("constraints", []):
        actual_facts.append(f"constraint: {constraint}")
    
    for pref in actual_output.get("preferences", []):
        actual_facts.append(f"preference: {pref}")
    
    for topic in actual_output.get("pending_topics", []):
        if isinstance(topic, str):
            actual_facts.append(f"pending_topic: {topic}")
        else:
            actual_facts.append(f"pending_topic: {topic.get('topic', str(topic))}")
    
    # Normalize for comparison
    expected_normalized = [f.lower().strip() for f in expected_facts]
    actual_normalized = [f.lower().strip() for f in actual_facts]
    
    # Simple overlap (not perfect, but good for quick testing)
    tp = 0
    for expected in expected_normalized:
        # Check if any actual fact contains the key content
        expected_content = expected.split(":", 1)[-1].strip()
        for actual in actual_normalized:
            actual_content = actual.split(":", 1)[-1].strip()
            if expected_content in actual_content or actual_content in expected_content:
                tp += 1
                break
    
    fp = len(actual_facts) - tp
    fn = len(expected_facts) - tp
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "expected_facts": expected_facts,
        "actual_facts": actual_facts
    }


class TestMemoryExtraction:
    """Test suite for memory extraction."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures."""
        self.memory_service = MemoryService()
        self.test_cases = load_test_cases()
    
    @pytest.mark.asyncio
    async def test_simple_extraction(self):
        """Test: Basic customer segment extraction."""
        test_case = next(tc for tc in self.test_cases if tc["id"] == "test_001_simple_extraction")
        
        existing = BusinessInsights(**test_case["existing_memory"])
        messages = parse_conversation(test_case["conversation"])
        
        result = await self.memory_service.extract_business_facts(
            existing_insights=existing,
            messages=messages
        )
        
        # Check that customer_segments was populated
        assert len(result.canvas_state["customer_segments"]) > 0, \
            "Expected customer_segments to be populated"
        
        # Check metrics
        metrics = compute_fact_overlap(
            test_case["expected_facts"],
            result.model_dump()
        )
        print(f"\n  📊 Metrics: Precision={metrics['precision']:.2f}, Recall={metrics['recall']:.2f}, F1={metrics['f1']:.2f}")
        assert metrics["recall"] >= 0.5, f"Recall too low: {metrics}"
    
    @pytest.mark.asyncio
    async def test_no_extraction_chit_chat(self):
        """Test: Chit-chat should not modify memory."""
        test_case = next(tc for tc in self.test_cases if tc["id"] == "test_002_no_extraction")
        
        existing = BusinessInsights(**test_case["existing_memory"])
        messages = parse_conversation(test_case["conversation"])
        
        result = await self.memory_service.extract_business_facts(
            existing_insights=existing,
            messages=messages
        )
        
        # Memory should be unchanged
        print(f"\n  ✅ Memory unchanged (as expected for chit-chat)")
        assert result.model_dump() == existing.model_dump(), \
            "Memory should not change for chit-chat"
    
    @pytest.mark.asyncio
    async def test_constraint_extraction(self):
        """Test: User rejection should become constraint."""
        test_case = next(tc for tc in self.test_cases if tc["id"] == "test_003_constraint_extraction")
        
        existing = BusinessInsights(**test_case["existing_memory"])
        messages = parse_conversation(test_case["conversation"])
        
        result = await self.memory_service.extract_business_facts(
            existing_insights=existing,
            messages=messages
        )
        
        # Check that constraint was added
        constraint_text = " ".join(result.constraints).lower()
        metrics = compute_fact_overlap(
            test_case["expected_facts"],
            result.model_dump()
        )
        print(f"\n  📊 Metrics: Precision={metrics['precision']:.2f}, Recall={metrics['recall']:.2f}, F1={metrics['f1']:.2f}")
        assert "subscription" in constraint_text or "no subscription" in constraint_text, \
            f"Expected subscription constraint, got: {result.constraints}"
    
    @pytest.mark.asyncio
    async def test_conflict_resolution(self):
        """Test: User changing mind should replace old fact."""
        test_case = next(tc for tc in self.test_cases if tc["id"] == "test_004_conflict_resolution")
        
        existing = BusinessInsights(**test_case["existing_memory"])
        messages = parse_conversation(test_case["conversation"])
        
        result = await self.memory_service.extract_business_facts(
            existing_insights=existing,
            messages=messages
        )
        
        segments = " ".join(result.canvas_state["customer_segments"]).lower()
        metrics = compute_fact_overlap(
            test_case["expected_facts"],
            result.model_dump()
        )
        print(f"\n  📊 Metrics: Precision={metrics['precision']:.2f}, Recall={metrics['recall']:.2f}, F1={metrics['f1']:.2f}")
        # Old segment should be replaced
        assert "millennial" in segments, \
            f"Expected Millennials in segments, got: {result.canvas_state['customer_segments']}"
    
    @pytest.mark.asyncio  
    async def test_non_agreement_handling(self):
        """Test: 'Maybe' should go to pending_topics, not main canvas."""
        test_case = next(tc for tc in self.test_cases if tc["id"] == "test_006_non_agreement")
        
        existing = BusinessInsights(**test_case["existing_memory"])
        messages = parse_conversation(test_case["conversation"])
        
        result = await self.memory_service.extract_business_facts(
            existing_insights=existing,
            messages=messages
        )
        
        # Should NOT add athletes to customer_segments
        segments = " ".join(result.canvas_state["customer_segments"]).lower()
        metrics = compute_fact_overlap(
            test_case["expected_facts"],
            result.model_dump()
        )
        print(f"\n  📊 Metrics: Precision={metrics['precision']:.2f}, Recall={metrics['recall']:.2f}, F1={metrics['f1']:.2f}")
        assert "athlete" not in segments, \
            f"Should not extract uncertain facts: {result.canvas_state['customer_segments']}"
    
    @pytest.mark.asyncio
    async def test_explicit_agreement(self):
        """Test: User explicitly agreeing to expert suggestion should extract."""
        test_case = next(tc for tc in self.test_cases if tc["id"] == "test_010_explicit_agreement")
        
        existing = BusinessInsights(**test_case["existing_memory"])
        messages = parse_conversation(test_case["conversation"])
        
        result = await self.memory_service.extract_business_facts(
            existing_insights=existing,
            messages=messages
        )
        
        channels = " ".join(result.canvas_state["channels"]).lower()
        metrics = compute_fact_overlap(
            test_case["expected_facts"],
            result.model_dump()
        )
        print(f"\n  📊 Metrics: Precision={metrics['precision']:.2f}, Recall={metrics['recall']:.2f}, F1={metrics['f1']:.2f}")
        assert "instagram" in channels or "tiktok" in channels, \
            f"Expected social channels, got: {result.canvas_state['channels']}"



class TestMetricComputation:
    """Test the metric computation logic."""
    
    def test_perfect_extraction(self):
        """Test perfect extraction yields F1=1.0."""
        expected = ["customer_segments: Small business owners"]
        actual = {
            "canvas_state": {
                "customer_segments": ["Small business owners"],
                "value_propositions": []
            },
            "constraints": [],
            "preferences": [],
            "pending_topics": []
        }
        
        metrics = compute_fact_overlap(expected, actual)
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1"] == 1.0
    
    def test_missed_fact(self):
        """Test missed fact reduces recall."""
        expected = ["customer_segments: SMBs", "channels: Direct sales"]
        actual = {
            "canvas_state": {
                "customer_segments": ["SMBs"],
                "channels": []  # Missing!
            },
            "constraints": [],
            "preferences": [],
            "pending_topics": []
        }
        
        metrics = compute_fact_overlap(expected, actual)
        assert metrics["recall"] < 1.0
        assert metrics["fn"] >= 1
    
    def test_hallucination(self):
        """Test hallucination reduces precision."""
        expected = ["customer_segments: SMBs"]
        actual = {
            "canvas_state": {
                "customer_segments": ["SMBs", "Enterprise clients"]  # Extra!
            },
            "constraints": [],
            "preferences": [],
            "pending_topics": []
        }
        
        metrics = compute_fact_overlap(expected, actual)
        assert metrics["precision"] < 1.0
        assert metrics["fp"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
