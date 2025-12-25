"""
Proactive Suggestion Service

Analyzes memory deltas and generates cross-canvas suggestions.
This service powers the "System Narrator" feature that provides
proactive hints without mixing expert personas.
"""

import json
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass

from langchain_google_genai import ChatGoogleGenerativeAI
from bmc.config import settings

logger = logging.getLogger(__name__)

# Cross-canvas implication rules
_CANVAS_IMPLICATIONS = {
    "customer_segments": ["channels", "customer_relationships", "value_propositions"],
    "value_propositions": ["customer_segments", "revenue_streams", "key_activities"],
    "channels": ["customer_relationships", "key_partnerships"],
    "customer_relationships": ["channels", "key_resources"],
    "revenue_streams": ["value_propositions", "cost_structure"],
    "key_resources": ["key_activities", "key_partnerships", "cost_structure"],
    "key_activities": ["key_resources", "key_partnerships", "cost_structure"],
    "key_partnerships": ["key_activities", "key_resources", "channels"],
    "cost_structure": ["key_resources", "key_activities", "revenue_streams"],
}

_PROACTIVE_SUGGESTION_PROMPT = """
You are a Business Model Canvas Advisor providing cross-canvas insights.

A user just made a change to their Business Model Canvas.

---
### MEMORY DELTA (What Changed)
{delta}

### CURRENT CANVAS STATE
{canvas_state}

### USER SECTOR
{sector}
---

YOUR TASK:
Determine if this change has **strong, obvious implications** for OTHER canvas blocks.

RULES:
1. Only suggest if there's a CLEAR, HIGH-VALUE connection.
2. Be specific and actionable.
3. Keep suggestions under 30 words.
4. If no clear implication exists, return null.

EXAMPLES OF GOOD SUGGESTIONS:
- "Adding 'Enterprise' to segments often requires 'Direct Sales' in Channels."
- "A 'Freemium' revenue model typically needs 'Product-Led Growth' in your Channels."
- "With 'AI/ML capabilities' as a resource, consider 'API Access' as an additional revenue stream."

OUTPUT FORMAT (JSON only, no markdown):
{{
  "suggestion": "Your specific suggestion here" | null,
  "target_block": "channels" | "customer_segments" | ... | null,
  "confidence": 0.0-1.0
}}
"""


@dataclass
class ProactiveSuggestion:
    """A proactive suggestion for the user."""
    suggestion: Optional[str]
    target_block: Optional[str]
    confidence: float = 0.0
    
    @property
    def should_show(self) -> bool:
        """Returns True if this suggestion should be shown to the user."""
        return self.suggestion is not None and self.confidence >= 0.6


class ProactiveService:
    """Service that generates proactive suggestions based on memory deltas."""
    
    def __init__(self):
        # Use Flash Lite for speed and cost-efficiency
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_LLM_MODEL_CONTEXT_SUMMARY,  # Flash Lite
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.3,  # Slight creativity for suggestions
        )
    
    def _has_cross_canvas_potential(self, delta: Dict) -> bool:
        """Quick check if the delta affects blocks with known implications."""
        if not delta or not delta.get("added"):
            return False
            
        added = delta.get("added", {})
        for block in added.keys():
            if block in _CANVAS_IMPLICATIONS:
                return True
        return False
    
    async def generate_suggestion(
        self,
        delta: Dict,
        canvas_state: Dict,
        sector: str,
        user_token: str = "unknown"
    ) -> ProactiveSuggestion:
        """
        Generate a proactive suggestion based on what changed.
        
        Args:
            delta: What changed in this turn {"added": {...}, "removed": {...}}
            canvas_state: Current state of all 9 canvas blocks
            sector: User's business sector
            user_token: For logging/tracing
            
        Returns:
            ProactiveSuggestion with suggestion text (or None) and target block
        """
        # Fast path: Skip LLM if no cross-canvas potential
        if not self._has_cross_canvas_potential(delta):
            logger.debug("Proactive Service: No cross-canvas potential, skipping LLM.")
            return ProactiveSuggestion(suggestion=None, target_block=None, confidence=0.0)
        
        try:
            prompt = _PROACTIVE_SUGGESTION_PROMPT.format(
                delta=json.dumps(delta, indent=2),
                canvas_state=json.dumps(canvas_state, indent=2),
                sector=sector or "General"
            )
            
            response = await self.llm.ainvoke(
                prompt,
                config={
                    "tags": ["proactive_suggestion", "system_narrator"],
                    "metadata": {
                        "user_token": user_token,
                        "service": "ProactiveService"
                    }
                }
            )
            
            # Parse JSON response
            content = str(response.content).strip()
            # Clean up markdown if present
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(content)
            
            suggestion = ProactiveSuggestion(
                suggestion=data.get("suggestion"),
                target_block=data.get("target_block"),
                confidence=float(data.get("confidence", 0.5))
            )
            
            if suggestion.should_show:
                logger.info(f"💡 Proactive Service: Generated suggestion for {suggestion.target_block}")
            else:
                logger.debug("Proactive Service: Suggestion below confidence threshold.")
                
            return suggestion
            
        except json.JSONDecodeError as e:
            logger.warning(f"Proactive Service: Failed to parse LLM response as JSON: {e}")
            return ProactiveSuggestion(suggestion=None, target_block=None, confidence=0.0)
        except Exception as e:
            logger.error(f"Proactive Service Error: {e}")
            return ProactiveSuggestion(suggestion=None, target_block=None, confidence=0.0)


# Singleton instance
proactive_service = ProactiveService()
