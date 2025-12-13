from langchain_core.messages import RemoveMessage, AIMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
import base64
import filetype
from jinja2 import Template
from langsmith import traceable
from google.genai import types

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

@traceable(name="native_gemini_generate", run_type="llm")
async def _generate_with_native_sdk(client, model_name, contents, config):
    """Wrapped generation call for LangSmith tracing."""
    return await client.aio.models.generate_content(
        model=model_name,
        contents=contents,
        config=config
    )

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


async def business_conversation_node(state: BusinessCanvasState, config: RunnableConfig):
    """Business canvas expert conversation node using Native Gemini SDK.
    
    Replaces LangChain wrapper to enable Native Grounding (Google Search)
    and Native Multimodal support without abstraction layers.
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

    # 4. Call Native SDK
    client = get_native_client()
    
    # Configure tools: Native Google Search Grounding
    # This dictionary configuration is what the API expects natively.
    # Note: The key is "google_search", not "google_search_retrieval" in newer API versions.
    tool_config = {
        "tools": [{"google_search": {}}],
        "system_instruction": rendered_system_prompt
    }

    try:
        logger.info("Invoking Native Gemini SDK with Grounding enabled")
        response = await _generate_with_native_sdk(
            client=client,
            model_name=settings.GEMINI_LLM_MODEL,
            contents=native_contents,
            config=tool_config
        )
        
        # 5. Handle Response
        # Extract text. The SDK usually handles citation merging in .text
        # If grounding metadata exists, it is in response.candidates[0].grounding_metadata
        final_text = response.text
        
        # Optional: Append citation notice if grounding happened?
        # For now, we trust .text contains the answer.
        
        return {
            "messages": [AIMessage(content=final_text)],
            "image_name": state.get("image_name"),
            "pdf_name": state.get("pdf_name"),
        }

    except Exception as e:
        logger.error(f"Native SDK Generation failed: {e}")
        return {
            "messages": [AIMessage(content="I apologize, but I encountered an error connecting to my knowledge base.")],
            "image_name": state.get("image_name"),
            "pdf_name": state.get("pdf_name"),
        }


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

