from typing_extensions import Literal

from langgraph.graph import END

from bmc.application.conversation_service.workflow.state import BusinessCanvasState
from bmc.config import settings


def should_summarize_business_conversation(
    state: BusinessCanvasState,
) -> Literal["business_summarize_conversation_node", "__end__"]:
    """Business canvas conversation summarization decision."""
    messages = state["messages"]

    if len(messages) > settings.TOTAL_MESSAGES_SUMMARY_TRIGGER:
        return "business_summarize_conversation_node"

    return END # type: ignore
