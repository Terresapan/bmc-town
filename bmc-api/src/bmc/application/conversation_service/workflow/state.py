from langgraph.graph import MessagesState
from typing import Optional, Dict, Any


class BusinessCanvasState(MessagesState):
    """State class for the LangGraph workflow for Business Canvas Expert conversations.

    Attributes:
        expert_context (str): The business context and expertise of the expert.
        expert_name (str): The name of the business expert.
        expert_domain (str): The Business Model Canvas component they specialize in.
        expert_perspective (str): The expert's approach and expertise.
        expert_style (str): The expert's communication style.
        user_context (Optional[Dict[str, Any]]): The business user's context and profile.
        user_token (Optional[str]): The business user token for security validation.
        summary (str): A summary of the conversation. This is used to reduce the token usage of the model.
        pdf_base64 (Optional[str]): Base64 encoded PDF for processing.
        image_base64 (Optional[str]): Base64 encoded image for processing.
        pdf_name (Optional[str]): Name of the PDF file.
        file_processing_completed (bool): Whether file processing has been completed.
        memory_delta (Optional[Dict]): Changes detected by memory extraction node.
        proactive_suggestion (Optional[str]): Cross-canvas suggestion from proactive node.
        proactive_target_block (Optional[str]): Which canvas block the suggestion targets.
    """

    expert_context: str
    expert_name: str
    expert_domain: str
    expert_perspective: str
    expert_style: str
    user_context: Optional[Dict[str, Any]]
    user_token: Optional[str] = None
    summary: str
    pdf_base64: Optional[str] = None
    image_base64: Optional[str] = None
    pdf_name: Optional[str] = None
    image_name: Optional[str] = None
    file_processing_completed: bool = False
    # New fields for proactive architecture
    memory_delta: Optional[Dict[str, Any]] = None
    proactive_suggestion: Optional[str] = None
    proactive_target_block: Optional[str] = None


def business_state_to_str(state: BusinessCanvasState) -> str:
    if "summary" in state and bool(state["summary"]):
        conversation = state["summary"]
    elif "messages" in state and bool(state["messages"]):
        conversation = state["messages"]
    else:
        conversation = ""

    user_info = state.get("user_context", {})
    user_business = user_info.get("business_name", "Unknown") if user_info else "Unknown"

    return f"""
            BusinessCanvasState(expert_context={state["expert_context"]}, 
            expert_name={state["expert_name"]}, 
            expert_domain={state["expert_domain"]}, 
            expert_perspective={state["expert_perspective"]}, 
            expert_style={state["expert_style"]}, 
            user_business={user_business},
            conversation={conversation})
        """
