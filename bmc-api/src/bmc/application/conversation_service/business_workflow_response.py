import uuid
from typing import Any, AsyncGenerator, Union, Dict, Optional
from bmc.config import settings
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, BaseMessage
from langgraph.checkpoint.mongodb import MongoDBSaver
# from langgraph.checkpoint.memory import InMemorySaver
from bmc.application.conversation_service.workflow.graph import (
    create_business_workflow_graph,
)
from bmc.application.conversation_service.workflow.state import BusinessCanvasState

# checkpointer = InMemorySaver()

def _extract_message_content(message: BaseMessage) -> str:
    """Safely extract text content from a message, handling strings, lists, and tool calls."""
    content = message.content
    
    # 1. Handle simple string
    if isinstance(content, str):
        if content:
            return content
        # If empty string but has tool_calls, return a status indicator
        if hasattr(message, "tool_calls") and message.tool_calls:
            # Check if it's a Google Search grounding call
            for tool in message.tool_calls:
                if tool.get("name") == "googleSearchRetrieval":
                    return "[Searching Google...]"
            return "[Using Tool...]"
        return ""

    # 2. Handle list of content parts (multimodal/complex response)
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)
        return "".join(text_parts)

    return ""


async def get_business_response(
    messages: str | list[str] | list[dict[str, Any]],
    expert_id: str,
    expert_name: str,
    expert_domain: str,
    expert_perspective: str,
    expert_style: str,
    expert_context: str,
    user_token: str,
    user_context: Optional[Dict[str, Any]] = None,
    image_base64: Optional[str] = None,
    pdf_base64: Optional[str] = None,
    pdf_name: Optional[str] = None,
    image_name: Optional[str] = None,
    new_thread: bool = False,
) -> tuple[str, BusinessCanvasState]:
    """Run a business canvas conversation through the workflow graph.

    Args:
        messages: Initial message to start the conversation.
        expert_id: Unique identifier for the business expert.
        expert_name: Name of the business expert.
        expert_domain: Business Model Canvas component domain.
        expert_perspective: Expert's approach and expertise.
        expert_style: Style of conversation.
        expert_context: Additional context about the expert.
        user_token: Unique identifier for the user to isolate conversations.
        user_context: Business user context and profile.
        image_base64: Optional base64 encoded image to include in the context.
        new_thread: Whether to create a new conversation thread.

    Returns:
        tuple[str, BusinessCanvasState]: A tuple containing:
            - The content of the last message in the conversation.
            - The final state after running the workflow.

    Raises:
        RuntimeError: If there's an error running the conversation workflow.
    """

    graph_builder = create_business_workflow_graph()

    try:
        with MongoDBSaver.from_conn_string(
            conn_string=settings.MONGODB_URI, 
            db_name=settings.MONGODB_DB_NAME, 
            checkpoint_collection_name=settings.MONGO_STATE_CHECKPOINT_COLLECTION, 
            writes_collection_name=settings.MONGO_STATE_WRITES_COLLECTION,
            ttl=3600,
        ) as checkpointer:
            graph = graph_builder.compile(checkpointer=checkpointer)

            # Generate thread ID using expert ID and user token
            thread_id = f"{expert_id}:{user_token}"
            
            # Append UUID if starting new thread
            if new_thread:
                thread_id = f"{thread_id}:{uuid.uuid4()}"
            config = {
                "configurable": {"thread_id": thread_id},
            }

            # Format messages - file processing now happens inside the workflow
            formatted_messages = __format_messages(messages=messages)
            
            # File processing is now handled inside the LangGraph workflow for unified tracing
            # Pass file data as part of the workflow state instead of processing outside
            workflow_input = {
                "messages": formatted_messages,
                "expert_context": expert_context,
                "expert_name": expert_name,
                "expert_domain": expert_domain,
                "expert_perspective": expert_perspective,
                "expert_style": expert_style,
                "user_context": user_context,
                "user_token": user_token,  # Include for business security validation
                "pdf_base64": pdf_base64,
                "image_base64": image_base64,
                "pdf_name": pdf_name,
                "image_name": image_name,
                "file_processing_completed": False,  # Start with files unprocessed
            }
            
            # The LangGraph workflow execution will be automatically traced by LangSmith
            # All file processing will be nested within this main trace
            output_state = await graph.ainvoke(
                input=workflow_input,
                config=config, # type: ignore
            )
            last_message = output_state["messages"][-1]
            
            response_text = _extract_message_content(last_message)
            return response_text, BusinessCanvasState(**output_state)
    except Exception as e:
        raise RuntimeError(f"Error running business conversation workflow: {str(e)}") from e


async def get_business_streaming_response(
    messages: str | list[str] | list[dict[str, Any]],
    expert_id: str,
    expert_name: str,
    expert_domain: str,
    expert_perspective: str,
    expert_style: str,
    expert_context: str,
    user_token: str,
    user_context: Optional[Dict[str, Any]] = None,
    image_base64: Optional[str] = None,
    pdf_base64: Optional[str] = None,
    pdf_name: Optional[str] = None,
    image_name: Optional[str] = None,
    new_thread: bool = False,
) -> AsyncGenerator[str, None]:
    """Run a business canvas conversation through the workflow graph with streaming response.

    Args:
        messages: Initial message to start the conversation.
        expert_id: Unique identifier for the business expert.
        expert_name: Name of the business expert.
        expert_domain: Business Model Canvas component domain.
        expert_perspective: Expert's approach and expertise.
        expert_style: Style of conversation.
        expert_context: Additional context about the expert.
        user_token: Unique identifier for the user to isolate conversations.
        user_context: Business user context and profile.
        image_base64: Optional base64 encoded image to include in the context.
        new_thread: Whether to create a new conversation thread.

    Yields:
        Chunks of the response as they become available.

    Raises:
        RuntimeError: If there's an error running the conversation workflow.
    """
    graph_builder = create_business_workflow_graph()

    try:
        with MongoDBSaver.from_conn_string(
            conn_string=settings.MONGODB_URI,
            db_name=settings.MONGODB_DB_NAME,
            checkpoint_collection_name=settings.MONGO_STATE_CHECKPOINT_COLLECTION,
            writes_collection_name=settings.MONGO_STATE_WRITES_COLLECTION,
            ttl=3600,
        ) as checkpointer:
            graph = graph_builder.compile(checkpointer=checkpointer)

            # Generate thread ID using expert ID and user token
            thread_id = f"{expert_id}:{user_token}"
            
            # Append UUID if starting new thread
            if new_thread:
                thread_id = f"{thread_id}:{uuid.uuid4()}"
            config = {
                "configurable": {"thread_id": thread_id},
            }

            # Streaming workflow execution will be automatically traced by LangGraph
            # Note: File processing IS supported in streaming mode now
            async for chunk in graph.astream(
                input={
                    "messages": __format_messages(messages=messages),
                    "expert_context": expert_context,
                    "expert_name": expert_name,
                    "expert_domain": expert_domain,
                    "expert_perspective": expert_perspective,
                    "expert_style": expert_style,
                    "user_context": user_context,
                    "user_token": user_token,  # Include for business security validation
                    "pdf_base64": pdf_base64,
                    "image_base64": image_base64,
                    "pdf_name": pdf_name,
                    "image_name": image_name,
                    "file_processing_completed": False,
                },
                config=config, # type: ignore
                stream_mode="messages",
            ):
                # Handle both chunks (if streaming) and full messages (if native SDK)
                if chunk[1]["langgraph_node"] == "business_conversation_node":
                    msg = chunk[0]
                    if isinstance(msg, (AIMessageChunk, AIMessage)):
                        content = _extract_message_content(msg)
                        if content:
                            yield content

    except Exception as e:
        raise RuntimeError(
            f"Error running streaming business conversation workflow: {str(e)}"
        ) from e


def __format_messages(
    messages: Union[str, list[str], list[dict[str, Any]]],
) -> list[Union[HumanMessage, AIMessage]]:
    """Convert various message formats to a list of LangChain message objects.

    Args:
        messages: Can be one of:
            - A single string message
            - A list of string messages
            - A list of dictionaries with 'role' and 'content' keys

    Returns:
        List[Union[HumanMessage, AIMessage]]: A list of LangChain message objects
    """

    if isinstance(messages, str):
        return [HumanMessage(content=messages)]

    if isinstance(messages, list):
        if not messages:
            return []

        # Check if it's a list of dictionaries with role/content
        if (
            isinstance(messages[0], dict)
            and "role" in messages[0]
            and "content" in messages[0]
        ):
            result = []
            for msg in messages:
                if msg["role"] == "user": # type: ignore
                    result.append(HumanMessage(content=str(msg["content"]))) # type: ignore
                elif msg["role"] == "assistant": # type: ignore
                    result.append(AIMessage(content=str(msg["content"]))) # type: ignore
            return result

        # Otherwise treat as list of strings
        return [HumanMessage(content=str(message)) for message in messages]

    return []