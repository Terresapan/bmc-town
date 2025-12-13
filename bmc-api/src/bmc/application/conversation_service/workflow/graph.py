from functools import lru_cache
from typing import Literal

from langgraph.graph import END, START, StateGraph

from bmc.application.conversation_service.workflow.edges import (
    should_summarize_business_conversation,
)
from bmc.application.conversation_service.workflow.nodes import (
    business_conversation_node,
    business_summarize_conversation_node,
    file_processing_node,
)
from bmc.application.conversation_service.workflow.state import BusinessCanvasState
from bmc.config import settings


def has_files_to_process(state: BusinessCanvasState) -> Literal["file_processing", "business_conversation"]:
    """Determine if file processing is needed based on state."""
    has_pdf = bool(state.get("pdf_base64"))
    has_image = bool(state.get("image_base64"))
    
    # If files are present, go through file processing node first
    if has_pdf or has_image:
        return "file_processing"
    else:
        return "business_conversation"


@lru_cache(maxsize=1)
def create_business_workflow_graph():
    """Create the Business Model Canvas workflow graph with integrated file processing."""
    graph_builder = StateGraph(BusinessCanvasState)

    # Add all nodes
    graph_builder.add_node("file_processing_node", file_processing_node)
    graph_builder.add_node("business_conversation_node", business_conversation_node)
    graph_builder.add_node("business_summarize_conversation_node", business_summarize_conversation_node)

    # Define the business workflow flow
    graph_builder.add_edge(START, "file_processing_node")
    graph_builder.add_conditional_edges(
        "file_processing_node", 
        has_files_to_process,
        {
            "file_processing": "business_conversation_node",  # Process files then go to conversation
            "business_conversation": "business_conversation_node"  # Skip file processing, go directly to conversation
        }
    )
    
    # Linear flow: Conversation -> Summarize Check -> [End, Summarize]
    # We removed the Tool Loop because Native Grounding handles search internally.
    graph_builder.add_conditional_edges(
        "business_conversation_node", 
        should_summarize_business_conversation
    )
    
    graph_builder.add_edge("business_summarize_conversation_node", END)
    
    return graph_builder


# Primary graph for Business Model Canvas 
graph = create_business_workflow_graph().compile()

