from typing import List, Dict
from pydantic import BaseModel, Field
import uuid


class BusinessInsights(BaseModel):
    """Structured semantic memory for the business user."""
    
    # 1. Semantic Memory (The BMC itself)
    canvas_state: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "customer_segments": [],
            "value_propositions": [],
            "channels": [],
            "customer_relationships": [],
            "revenue_streams": [],
            "key_resources": [],
            "key_activities": [],
            "key_partnerships": [],
            "cost_structure": [],
        },
        description="The current state of the 9 Business Model Canvas blocks."
    )

    # 2. Constraints (Negative Semantic Memory)
    constraints: List[str] = Field(
        default_factory=list, 
        description="Explicit boundaries or 'negative' facts (e.g., 'No subscription models')."
    )

    # 3. User Preferences (Meta-Memory)
    preferences: List[str] = Field(
        default_factory=list, 
        description="User interaction preferences (e.g., 'Prefers bullet points')."
    )

    # 4. Pending Topics (Working Memory)
    pending_topics: List[str] = Field(
        default_factory=list, 
        description="Open questions or topics to be resolved."
    )


class BusinessUser(BaseModel):
    """A class representing a simulated business user profile.

    Args:
        token (str): Access token for this user profile.
        owner_name (str): Name of the business owner.
        business_name (str): Name of the business.
        sector (str): Industry sector.
        challenges (List[str]): Current business challenges.
        goals (List[str]): Business goals and objectives.
        key_insights (BusinessInsights): Long-term semantic memory of the business model.
    """

    token: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Access token for this user profile")
    role: str = Field(default="user", description="User role (admin or user)")
    owner_name: str = Field(description="Name of the business owner")
    business_name: str = Field(description="Name of the business")
    sector: str = Field(description="Industry sector")
    challenges: List[str] = Field(description="Current business challenges")
    goals: List[str] = Field(description="Business goals and objectives")
    key_insights: BusinessInsights = Field(
        default_factory=BusinessInsights, 
        description="Shared living context/memory across experts."
    )

    def to_context_string(self) -> str:
        """Convert the business user profile to a formatted context string.
        
        This now includes the structured 'key_insights' (Shared Living Context).
        """
        
        # Format Canvas State
        canvas_str = ""
        has_canvas_data = False
        for block, items in self.key_insights.canvas_state.items():
            if items:
                has_canvas_data = True
                formatted_items = "\n  - ".join(items)
                readable_block = block.replace("_", " ").title()
                canvas_str += f"- {readable_block}:\n  - {formatted_items}\n"
        
        if not has_canvas_data:
            canvas_str = "(No business model facts recorded yet)"

        # Format Constraints & Preferences
        constraints_str = "\n".join([f"- {c}" for c in self.key_insights.constraints]) or "(None)"
        preferences_str = "\n".join([f"- {p}" for p in self.key_insights.preferences]) or "(None)"
        pending_str = "\n".join([f"- {t}" for t in self.key_insights.pending_topics]) or "(None)"

        return f"""
                CLIENT PROFILE:
                Name: {self.owner_name} (your client)
                Business: {self.business_name}
                Sector: {self.sector}
                Current Challenges: {', '.join(self.challenges)}
                Business Goals: {', '.join(self.goals)}
                
                === SHARED LIVING CONTEXT (LONG-TERM MEMORY) ===
                This section contains facts agreed upon with ALL other experts.
                
                [BUSINESS MODEL STATE]
                {canvas_str}
                
                [CONSTRAINTS & BOUNDARIES]
                {constraints_str}
                
                [USER PREFERENCES]
                {preferences_str}
                
                [PENDING TOPICS / OPEN QUESTIONS]
                {pending_str}
                
                Note: You are meeting with {self.owner_name.split()[0]} for a business consultation. 
                They are your established client and you should know their name.
                """

    def __str__(self) -> str:
        return f"BusinessUser(token={self.token}, business_name={self.business_name}, sector={self.sector})"
