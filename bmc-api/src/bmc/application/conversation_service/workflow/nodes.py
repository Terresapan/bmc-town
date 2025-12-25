from langchain_core.messages import RemoveMessage, AIMessage, AIMessageChunk, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
import base64
import filetype
from jinja2 import Template
from langsmith import traceable
from google.genai import types
from typing import AsyncGenerator

from bmc.application.conversation_service.workflow.chains import (
    get_business_conversation_summary_chain,
    get_native_client,
)

from bmc.application.conversation_service.workflow.state import BusinessCanvasState
from bmc.config import settings
from bmc.domain.business_user_factory import BusinessUserFactory
from bmc.domain.business_user import BusinessUser
from bmc.domain.prompts import BUSINESS_EXPERT_CHARACTER_CARD
from bmc.application.conversation_service.business_security import (
    business_validator,
    ValidationResult,
    BusinessContext,
)
from loguru import logger

def _sanitize_base64(b64_string: str | None) -> str | None:
    """Sanitize base64 string, handling Swagger placeholders and padding."""
    if not b64_string or b64_string == "string":
        return None
    
    # Fix padding if needed
    missing_padding = len(b64_string) % 4
    if missing_padding:
        b64_string += "=" * (4 - missing_padding)
    return b64_string

def _convert_to_native_content(
    messages: list[BaseMessage], 
    pdf_base64: str | None, 
    image_base64: str | None
) -> list[types.Content]:
    """Convert LangChain messages to Native Gemini SDK Content objects."""
    native_contents = []
    
    # Process history (all but last)
    history = messages[:-1] if messages else []
    for msg in history:
        role = "user" if isinstance(msg, HumanMessage) else "model"
        # Use constructor for robustness
        native_contents.append(
            types.Content(role=role, parts=[types.Part(text=msg.content)])
        )
    
    # Process current turn (last message) with potential file attachments
    if not messages:
        return native_contents
        
    last_msg = messages[-1]
    current_parts = []
    
    # Add text
    text_content = last_msg.content if isinstance(last_msg.content, str) else ""
    if isinstance(last_msg.content, list):
        # Extract text from complex LC content if needed
        for part in last_msg.content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_content = part["text"]
                break
    
    if text_content:
        current_parts.append(types.Part(text=text_content))
    
    # Add PDF if present
    if pdf_base64:
        try:
            pdf_data = base64.b64decode(pdf_base64)
            current_parts.append(
                types.Part(
                    inline_data=types.Blob(
                        data=pdf_data, 
                        mime_type="application/pdf"
                    )
                )
            )
            logger.info("Attached PDF to native content")
        except Exception as e:
            logger.error(f"Failed to attach PDF: {e}")

    # Add Image if present
    if image_base64:
        try:
            img_data = base64.b64decode(image_base64)
            # Simple mime detection fallback
            mime_type = "image/png"
            kind = filetype.guess(img_data)
            if kind:
                mime_type = kind.mime
            
            current_parts.append(
                types.Part(
                    inline_data=types.Blob(
                        data=img_data, 
                        mime_type=mime_type
                    )
                )
            )
            logger.info(f"Attached Image ({mime_type}) to native content")
        except Exception as e:
            logger.error(f"Failed to attach Image: {e}")

    native_contents.append(types.Content(role="user", parts=current_parts))
    
    return native_contents

@traceable(name="native_gemini_generate_stream", run_type="llm")
async def _generate_with_native_sdk_stream(
    client, 
    model_name: str, 
    contents, 
    config
) -> AsyncGenerator[tuple[str, dict], None]:
    """Streaming generation call with token usage tracking.
    
    Uses generate_content_stream for true token-by-token streaming.
    Yields (text_chunk, usage_metadata) tuples as they arrive from the Gemini API.
    
    The final chunk contains usage_metadata with token counts.
    """
    usage_metadata = {}
    
    async for chunk in await client.aio.models.generate_content_stream(
        model=model_name,
        contents=contents,
        config=config
    ):
        # Capture usage metadata if present (typically in final chunk)
        if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
            usage_metadata = {
                "input_tokens": getattr(chunk.usage_metadata, 'prompt_token_count', 0),
                "output_tokens": getattr(chunk.usage_metadata, 'candidates_token_count', 0),
                "total_tokens": getattr(chunk.usage_metadata, 'total_token_count', 0),
                "model": model_name,
            }
        
        # Extract text from streaming chunk
        if chunk.text:
            yield (chunk.text, usage_metadata)

@traceable(name="file_processing_node", run_type="chain")
async def file_processing_node(state: BusinessCanvasState):
    """Handle PDF and image processing validation within the LangGraph workflow.
    
    This node validates business context for file operations.
    Actual file content is now passed directly to the LLM via LangChain.
    """
    pdf_base64 = _sanitize_base64(state.get("pdf_base64"))
    image_base64 = _sanitize_base64(state.get("image_base64"))
    pdf_name = state.get("pdf_name")
    image_name = state.get("image_name")
    user_token = state.get("user_token")
       
    # If no files to process, just mark as completed
    if not pdf_base64 and not image_base64:
        return {
            "file_processing_completed": True,
            "image_name": image_name,  # Preserve image_name even if no base64
            "pdf_name": pdf_name,      # Preserve pdf_name even if no base64
        }
    
    logger.info(f"Validating file access in LangGraph workflow: PDF={bool(pdf_base64)}, Image={bool(image_base64)}")
    
    # Validate business context before processing files
    validation_result, business_context = await business_validator.validate_business_context(
        user_token, "file_processing_node"
    )
    
    if validation_result != ValidationResult.VALID:
        logger.error(f"Business validation failed in file processing node: {validation_result}")
        # Log failed attempt for audit
        if business_context:
            file_sizes = {
                "pdf": len(pdf_base64) if pdf_base64 else 0,
                "image": len(image_base64) if image_base64 else 0
            }
            
            if pdf_base64:
                business_validator.log_file_processing_audit(
                    business_context=business_context,
                    file_type="pdf",
                    file_name=pdf_name,
                    file_size=file_sizes["pdf"],
                    success=False,
                    error_message=f"Validation failed: {validation_result}"
                )
            if image_base64:
                business_validator.log_file_processing_audit(
                    business_context=business_context,
                    file_type="image",
                    file_name=image_name or "image",
                    file_size=file_sizes["image"],
                    success=False,
                    error_message=f"Validation failed: {validation_result}"
                )
        
        # Continue workflow but mark processing as failed
        return {
            "file_processing_completed": True,
            "file_processing_error": f"Business validation failed: {validation_result}",
            "image_name": image_name,  # Preserve image_name even on failure
            "pdf_name": pdf_name,      # Preserve pdf_name even on failure
        }
    
    # Log successful validation/access
    if business_context:
        if pdf_base64:
            business_validator.log_file_processing_audit(
                business_context=business_context,
                file_type="pdf",
                file_name=pdf_name,
                file_size=len(pdf_base64),
                success=True
            )
        if image_base64:
            business_validator.log_file_processing_audit(
                business_context=business_context,
                file_type="image",
                file_name=image_name or "image",
                file_size=len(image_base64),
                success=True
            )

    # Mark file processing as completed (validation passed)
    return {
        "file_processing_completed": True,
        "image_name": image_name,  # Preserve image_name in state
        "pdf_name": pdf_name,      # Preserve pdf_name in state  
    }


@traceable(name="business_conversation_node", run_type="chain")
async def business_conversation_node(state: BusinessCanvasState, config: RunnableConfig):
    """Business canvas expert conversation node using Native Gemini SDK with streaming.
    
    Replaces LangChain wrapper to enable Native Grounding (Google Search)
    and Native Multimodal support without abstraction layers.
    
    This is an async generator that yields AIMessageChunk objects for true
    token-by-token streaming in LangGraph.
    """
    summary = state.get("summary", "")

    # 1. Prepare User Context
    user_context_section = ""
    user_context_data = state.get("user_context")
    if user_context_data:
        try:
            user = BusinessUser(**user_context_data)
            user_context_section = BusinessUserFactory.format_user_context(user)
        except Exception as e:
            logger.error(f"Error reconstructing BusinessUser: {e}")
            user_context_section = "You're speaking with a business owner seeking guidance."
    else:
        user_context_section = BusinessUserFactory.format_user_context(None)

    # 2. Render System Prompt manually
    # We use Jinja2 to render the prompt template with state variables
    system_prompt_template = Template(BUSINESS_EXPERT_CHARACTER_CARD.prompt)
    rendered_system_prompt = system_prompt_template.render(
        expert_name=state["expert_name"],
        expert_domain=state["expert_domain"],
        expert_perspective=state["expert_perspective"],
        expert_style=state["expert_style"],
        user_context_section=user_context_section,  # Fixed: matches {{user_context_section}} in template
        summary=summary,  # Added: matches {{summary}} in template
    )



    # 3. Prepare Content (Text + Files)
    pdf_base64 = _sanitize_base64(state.get("pdf_base64"))
    image_base64 = _sanitize_base64(state.get("image_base64"))
    
    native_contents = _convert_to_native_content(
        state["messages"],
        pdf_base64,
        image_base64
    )

    # 4. Call Native SDK with Streaming
    client = get_native_client()
    
    # Configure tools: Native Google Search Grounding
    # This dictionary configuration is what the API expects natively.
    # Note: The key is "google_search", not "google_search_retrieval" in newer API versions.
    tool_config = {
        "tools": [{"google_search": {}}],
        "system_instruction": rendered_system_prompt
    }

    try:
        logger.info("Invoking Native Gemini SDK with Streaming and Grounding enabled")
        
        # Accumulate the full response for state update
        full_response_text = ""
        final_usage_metadata = {}
        
        # Stream chunks as AIMessageChunk for LangGraph compatibility
        async for text_chunk, usage_metadata in _generate_with_native_sdk_stream(
            client=client,
            model_name=settings.GEMINI_LLM_MODEL,
            contents=native_contents,
            config=tool_config
        ):
            full_response_text += text_chunk
            # Capture usage metadata (updated with each chunk, final value is accurate)
            if usage_metadata:
                final_usage_metadata = usage_metadata
            # Yield AIMessageChunk for streaming - LangGraph will emit these
            yield {
                "messages": [AIMessageChunk(content=text_chunk)],
            }
        
        # Log token usage for observability
        if final_usage_metadata:
            logger.info(f"🔢 Token Usage - Input: {final_usage_metadata.get('input_tokens', 0)}, "
                       f"Output: {final_usage_metadata.get('output_tokens', 0)}, "
                       f"Total: {final_usage_metadata.get('total_tokens', 0)}")
        
        # After streaming completes, yield final state update with complete message
        # This ensures checkpoint saves the full message
        yield {
            "messages": [AIMessage(content=full_response_text)],
            "image_name": state.get("image_name"),
            "pdf_name": state.get("pdf_name"),
        }

    except Exception as e:
        logger.error(f"Native SDK Streaming Generation failed: {e}")
        yield {
            "messages": [AIMessage(content="I apologize, but I encountered an error connecting to my knowledge base.")],
            "image_name": state.get("image_name"),
            "pdf_name": state.get("pdf_name"),
        }


@traceable(name="business_summarize_conversation_node", run_type="chain")
async def business_summarize_conversation_node(state: BusinessCanvasState):
    """Business expert conversation summary node."""
    summary = state.get("summary", "")
    summary_chain = get_business_conversation_summary_chain(summary)

    response = await summary_chain.ainvoke(
        {
            "messages": state["messages"],
            "expert_name": state["expert_name"],
            "summary": summary,
        }
    )

    delete_messages = [
        RemoveMessage(id=m.id) # type: ignore
        for m in state["messages"][: -settings.TOTAL_MESSAGES_AFTER_SUMMARY]
    ]
    return {
        "summary": response.content, 
        "messages": delete_messages,
        "image_name": state.get("image_name"),  # Preserve image_name
        "pdf_name": state.get("pdf_name"),      # Preserve pdf_name
    }


@traceable(name="memory_extraction_node", run_type="chain")
async def memory_extraction_node(state: BusinessCanvasState):
    """Extract business facts from the conversation and update user memory.
    
    This node:
    1. Loads the user from the database.
    2. Extracts facts from the conversation using the MemoryService.
    3. Updates the database with any changes.
    4. Returns the delta (what changed) for the proactive node.
    """
    from bmc.application.memory_service import memory_service
    
    user_token = state.get("user_token")
    if not user_token:
        logger.warning("Memory Extraction: No user token in state, skipping.")
        return {"memory_delta": None}
    
    try:
        # Get messages from state
        messages = state.get("messages", [])
        if not messages:
            logger.debug("Memory Extraction: No messages in state, skipping.")
            return {"memory_delta": None}
        
        # Extract facts and update DB
        result = await memory_service.update_user_memory(
            user_token=user_token,
            messages=messages
        )
        
        if result and result.has_changes:
            logger.info(f"🧠 Memory Extraction Node: Delta computed - {result.delta}")
            return {
                "memory_delta": result.delta,
            }
        else:
            logger.debug("Memory Extraction Node: No changes detected.")
            return {"memory_delta": None}
            
    except Exception as e:
        logger.error(f"Memory Extraction Node Error: {e}")
        return {"memory_delta": None}


@traceable(name="proactive_suggestion_node", run_type="chain")
async def proactive_suggestion_node(state: BusinessCanvasState):
    """Generate cross-canvas suggestions based on memory delta.
    
    This node:
    1. Checks if there was a memory delta from the previous node.
    2. If so, generates a proactive suggestion using the ProactiveService.
    3. If the suggestion is valuable, adds it to pending_topics.
    4. Returns the suggestion for the API to deliver via UI.
    """
    from bmc.application.proactive_service import proactive_service
    from bmc.domain.business_user_factory import BusinessUserFactory
    
    memory_delta = state.get("memory_delta")
    user_token = state.get("user_token")
    
    # Fast path: No delta, no suggestion
    if not memory_delta or not user_token:
        logger.debug("Proactive Suggestion Node: No delta or user token, skipping.")
        return {
            "proactive_suggestion": None,
            "proactive_target_block": None,
        }
    
    try:
        # Load user to get current canvas state and sector
        factory = BusinessUserFactory()
        user = await factory.get_user_by_token(user_token)
        
        if not user:
            logger.warning("Proactive Suggestion Node: User not found.")
            return {
                "proactive_suggestion": None,
                "proactive_target_block": None,
            }
        
        # Generate suggestion
        suggestion_result = await proactive_service.generate_suggestion(
            delta=memory_delta,
            canvas_state=user.key_insights.canvas_state,
            sector=user.sector,
            user_token=user_token
        )
        
        if suggestion_result.should_show:
            logger.info(f"💡 Proactive Suggestion Node: Generated suggestion for {suggestion_result.target_block}")
            
            # Add to pending_topics with [SYS] prefix for staging
            sys_topic = f"[SYS] {suggestion_result.suggestion}"
            if sys_topic not in user.key_insights.pending_topics:
                user.key_insights.pending_topics.append(sys_topic)
                await factory.update_user(user_token, user)
                logger.info(f"💾 Proactive Suggestion Node: Added to pending_topics")
            
            return {
                "proactive_suggestion": suggestion_result.suggestion,
                "proactive_target_block": suggestion_result.target_block,
            }
        else:
            logger.debug("Proactive Suggestion Node: No suggestion generated.")
            return {
                "proactive_suggestion": None,
                "proactive_target_block": None,
            }
            
    except Exception as e:
        logger.error(f"Proactive Suggestion Node Error: {e}")
        return {
            "proactive_suggestion": None,
            "proactive_target_block": None,
        }
