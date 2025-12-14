from typing import List, Dict, Optional
import json
import logging

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from bmc.config import settings
from bmc.domain.business_user import BusinessInsights

logger = logging.getLogger(__name__)

# Define the Prompt for Fact Extraction
_FACT_EXTRACTION_PROMPT = """
You are a meticulous Business Analyst and Fact-Checker.
Your goal is to maintain a "Shared Living Context" for a business user across multiple expert sessions.

You will be given:
1. The EXISTING MEMORY (Current state of the Business Model).
2. The RECENT CONVERSATION (The last few messages exchanged).

YOUR TASK:
Extract new facts, updates, or constraints from the RECENT CONVERSATION and merge them into the EXISTING MEMORY.

---
### 1. EXISTING MEMORY (JSON)
{existing_memory}

### 2. RECENT CONVERSATION
{conversation_text}
---

### EXTRACTION RULES:

#### Rule 1: Explicit Agreement Only
Only extract facts that the user has EXPLICITLY stated or agreed to.

**AGREEMENT INDICATORS (DO Extract):**
- Direct statements: "My customers are X", "We'll charge $99/month"
- Explicit confirmation: "Yes", "Correct", "That's right", "Let's do that", "Exactly"
- Affirmative action: "Let's focus on Instagram"

**NON-AGREEMENT (DO NOT Extract):**
- Uncertainty: "Maybe", "I'll think about it", "Not sure", "Possibly"
- Questions: "Should I target Gen Z?"
- Expert suggestions the user didn't respond to or confirm

#### Rule 2: Conflict Resolution
- If the user says something that contradicts the "Existing Memory", the **User's new statement WINS**. Replace the old fact.
- Keywords indicating replacement: "Actually", "Instead", "Changed my mind", "No longer"
- If the user explicitly rejects an idea (e.g., "No subscriptions"), add it to `constraints`.

#### Rule 3: Merge Behavior
- **ADDITIONS**: If user adds a new fact (e.g., "I also want to target..."), APPEND to existing list.
- **REPLACEMENTS**: If user changes their mind (e.g., "Actually, my target is..."), REPLACE the old value.
- **DELETIONS**: If user rejects something previously agreed, REMOVE it and add to `constraints`.

#### Rule 4: Categorization
- `canvas_state`: Map facts to the 9 BMC blocks (customer_segments, value_propositions, channels, customer_relationships, revenue_streams, key_resources, key_activities, key_partnerships, cost_structure).
- `constraints`: Hard boundaries the user has explicitly rejected or ruled out.
- `preferences`: User's interaction style preferences (e.g., "Be concise", "Use bullet points").
- `pending_topics`: Unresolved questions or items the user said they'd think about.

#### Rule 5: Minimalism
If the conversation was just chit-chat ("Hello", "Thanks", "Goodbye"), return the EXISTING MEMORY exactly as is. Do NOT hallucinate updates.

---
### FEW-SHOT EXAMPLES:

#### Example 1: Simple Extraction
CONVERSATION:
User: "My target customers are small business owners in the US."
Expert: "That's a clear segment!"

OUTPUT: Add "Small business owners in the US" to `canvas_state.customer_segments`.

#### Example 2: No Extraction Needed
CONVERSATION:
User: "Thanks for the help!"
Expert: "You're welcome!"

OUTPUT: Return EXISTING MEMORY unchanged. No business facts were discussed.

#### Example 3: Constraint Extraction
CONVERSATION:
Expert: "Have you considered a subscription model?"
User: "No, absolutely not. I only want one-time purchases."

OUTPUT: 
- Add "One-time purchases" to `canvas_state.revenue_streams`.
- Add "No subscription model" to `constraints`.

#### Example 4: Expert Suggestion - User Uncertain (Do NOT Extract)
CONVERSATION:
Expert: "You could partner with AWS for cloud infrastructure."
User: "Hmm, maybe. I'll think about it."

OUTPUT: 
- Do NOT add AWS to `key_partnerships` (user didn't confirm).
- Add "Consider AWS partnership" to `pending_topics`.

#### Example 5: User Changes Mind (Replace)
EXISTING MEMORY: customer_segments = ["Gen Z gamers"]
CONVERSATION:
User: "Actually, I've changed my mind. I want to target Millennials instead."

OUTPUT: REPLACE customer_segments with ["Millennials"]. The old value is overwritten.

---
### OUTPUT FORMAT
Return ONLY valid JSON matching the `BusinessInsights` schema structure. No markdown formatting.
IMPORTANT: `canvas_state` values must be LISTS OF STRINGS. Do not use objects/dictionaries inside the lists.
Example: "customer_segments": ["Gen Z Gamers", "Retro enthusiasts"]
"""

class MemoryService:
    def __init__(self):
        # Use Flash Lite for speed and cost-efficiency
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_LLM_MODEL_CONTEXT_SUMMARY,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0, # Deterministic for data extraction
        )

    async def extract_business_facts(
        self, 
        existing_insights: BusinessInsights, 
        messages: List[BaseMessage],
        user_token: str = "unknown"
    ) -> BusinessInsights:
        """
        Extracts business facts from the conversation and updates the insights.
        """
        try:
            # 1. Format Conversation History
            conversation_text = ""
            for msg in messages:
                role = "User" if isinstance(msg, HumanMessage) else "Expert"
                content = str(msg.content)
                conversation_text += f"{role}: {content}\n"

            # 2. Format Existing Memory as JSON string
            existing_memory_json = existing_insights.model_dump_json()

            # 3. Construct the Prompt
            prompt = _FACT_EXTRACTION_PROMPT.format(
                existing_memory=existing_memory_json,
                conversation_text=conversation_text
            )

            # 4. Invoke LLM with Observability Tags
            response = await self.llm.ainvoke(
                prompt,
                config={
                    "tags": ["memory_extraction", "background_task"],
                    "metadata": {
                        "user_token": user_token,
                        "service": "MemoryService"
                    }
                }
            )
            response_content = response.content
            
            # 5. Parse JSON
            if isinstance(response_content, str):
                cleaned_content = response_content.replace("```json", "").replace("```", "").strip()
                try:
                    data = json.loads(cleaned_content)
                    updated_insights = BusinessInsights(**data)
                    
                    if updated_insights.model_dump() != existing_insights.model_dump():
                        logger.info("🧠 Memory Service: Insights updated based on conversation.")
                    else:
                        logger.info("🧠 Memory Service: No new insights found.")
                        
                    return updated_insights

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON from Memory Service: {response_content}")
                    return existing_insights
                except Exception as e:
                     logger.error(f"Validation Error in Memory Service: {e}")
                     return existing_insights
            
            return existing_insights

        except Exception as e:
            logger.error(f"Error in MemoryService.extract_business_facts: {e}")
            return existing_insights

    async def update_user_memory(self, user_token: str, messages: List[BaseMessage]):
        """
        Main entry point for the Background Task.
        1. Loads the user.
        2. extracts facts.
        3. Updates the DB.
        """
        from bmc.domain.business_user_factory import BusinessUserFactory
        
        factory = BusinessUserFactory()
        
        try:
            # 1. Load User
            user = await factory.get_user_by_token(user_token)
            if not user:
                logger.warning(f"Memory Service: User not found for token {user_token}")
                return

            # 2. Extract Facts
            updated_insights = await self.extract_business_facts(
                existing_insights=user.key_insights,
                messages=messages,
                user_token=user_token
            )

            # 3. Update DB (Only if changed)
            if updated_insights != user.key_insights:
                user.key_insights = updated_insights
                await factory.update_user(user_token, user)
                logger.info(f"💾 Memory Service: Persisted updates for user {user.business_name}")

        except Exception as e:
            logger.error(f"CRITICAL: Failed to update user memory in background task: {e}")

memory_service = MemoryService()
