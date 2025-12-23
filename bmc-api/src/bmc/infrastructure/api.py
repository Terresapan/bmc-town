from contextlib import asynccontextmanager
from typing import List, Optional
import os
from fastapi import FastAPI, HTTPException, Query, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pydantic import BaseModel

from bmc.application.conversation_service.business_workflow_response import (
    get_business_response,
    get_business_streaming_response,
)
from bmc.application.memory_service import memory_service
from bmc.domain.business_expert_factory import BusinessExpertFactory
from bmc.domain.business_user_factory import (
    BusinessUserFactory,
    DatabaseConnectionError,
    DatabaseOperationError,
    UserAlreadyExistsError,
)
from bmc.domain.business_user import BusinessUser
from langchain_core.messages import HumanMessage, AIMessage

import logging
from bmc.config import settings
from urllib.parse import urlparse


# Configure logging
logging.basicConfig(level=logging.INFO)

# Log MongoDB host to verify correct URI
uri_host = urlparse(settings.MONGODB_URI).netloc
logging.info(f"MongoDB host in use: {uri_host}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database connection and create indexes
    try:
        await BusinessUserFactory.create_collection_with_index()
        print("✅ BusinessUserFactory initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize BusinessUserFactory: {e}")
        # You might want to fail startup if database is critical
        raise
    yield
    # Cleanup on shutdown
    try:
        await BusinessUserFactory.close_connections()
        print("🔌 BusinessUserFactory connections closed")
    except Exception as e:
        print(f"⚠️ Error closing database connections: {e}")


app = FastAPI(lifespan=lifespan)

# CORS configuration - allow specific origins when credentials are enabled
# Get allowed origins from environment or use defaults
allowed_origins = [
    "https://bmc-ui-635390037922.us-central1.run.app",  # New BMC UI
    "https://philoagents-ui-635390037922.us-central1.run.app",  # Legacy UI
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

# Add environment-specific origins if available
if "CORS_ORIGINS" in os.environ:
    allowed_origins.extend(os.environ["CORS_ORIGINS"].split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- THIS IS THE NEW HEALTH CHECK ENDPOINT ---
#
@app.get("/")
async def health_check():
    """A simple health check endpoint that Cloud Run can ping."""
    return {"status": "ok"}
#
# --- END OF NEW SECTION ---

# --- DIAGNOSTIC ENDPOINT FOR DATABASE CONNECTIVITY ---
#
@app.get("/diagnostics/database")
async def database_diagnostics():
    """Diagnostic endpoint to check database connectivity and status."""
    try:
        user_factory = BusinessUserFactory()
        
        # Test connection by getting user count
        user_count = await user_factory.get_users_count()
        
        # Test by fetching all users (should return empty array if none exist)
        users = await user_factory.get_all_users()
        
        # Get MongoDB host info from settings
        uri_host = urlparse(settings.MONGODB_URI).netloc
        
        return {
            "status": "healthy",
            "database": {
                "host": uri_host,
                "connected": True,
                "user_count": user_count,
                "users_loaded": len(users)
            },
            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
        }
    except DatabaseConnectionError as e:
        return {
            "status": "unhealthy",
            "database": {
                "connected": False,
                "error": f"Connection error: {str(e)}"
            },
            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": {
                "connected": False,
                "error": f"Unexpected error: {str(e)}"
            },
            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
        }
#
# --- END DIAGNOSTIC ENDPOINT ---

class BusinessChatMessage(BaseModel):
    message: str
    expert_id: str
    user_token: str
    image_base64: Optional[str] = None
    pdf_base64: Optional[str] = None
    pdf_name: Optional[str] = None
    image_name: Optional[str] = None


@app.post("/chat/business")
async def business_chat(
    chat_message: BusinessChatMessage, 
    background_tasks: BackgroundTasks
):
    """Chat with a Business Canvas expert."""
    try:
        expert_factory = BusinessExpertFactory()
        expert = expert_factory.get_expert(chat_message.expert_id)

        # Get user context if token provided
        user_context = None
        if chat_message.user_token:
            try:
                user_factory = BusinessUserFactory()
                user = await user_factory.get_user_by_token(chat_message.user_token)
                if user:
                    user_context = user.model_dump()
            except (DatabaseConnectionError, DatabaseOperationError) as e:
                # Continue without user context if database issues occur
                print(f"Warning: Could not retrieve user context: {e}")

        response, state = await get_business_response(
            messages=chat_message.message,
            expert_id=chat_message.expert_id,
            expert_name=expert.name,
            expert_domain=expert.domain,
            expert_perspective=expert.perspective,
            expert_style=expert.style,
            expert_context=f"Domain: {expert.domain}. Expertise: {expert.perspective}",
            user_token=chat_message.user_token,
            user_context=user_context,
            image_base64=chat_message.image_base64,
            pdf_base64=chat_message.pdf_base64,
            pdf_name=chat_message.pdf_name,
            image_name=chat_message.image_name,
        )

        # --- MEMORY EXTRACTION (BACKGROUND) ---
        # Trigger the "Shared Living Context" update
        if chat_message.user_token:
            # Construct the conversation pair (User Request + AI Response)
            # This is what the Memory Service needs to extract facts.
            conversation_pair = [
                HumanMessage(content=chat_message.message),
                AIMessage(content=response)
            ]
            
            background_tasks.add_task(
                memory_service.update_user_memory,
                user_token=chat_message.user_token,
                messages=conversation_pair
            )
        # --------------------------------------

        return {"response": response}
    except Exception as e:


        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/business/stream")
async def business_chat_stream(
    chat_message: BusinessChatMessage,
    background_tasks: BackgroundTasks
):
    """Chat with a Business Canvas expert with streaming response."""
    try:
        expert_factory = BusinessExpertFactory()
        expert = expert_factory.get_expert(chat_message.expert_id)

        # Get user context if token provided
        user_context = None
        if chat_message.user_token:
            try:
                user_factory = BusinessUserFactory()
                user = await user_factory.get_user_by_token(chat_message.user_token)
                if user:
                    user_context = user.model_dump()
            except (DatabaseConnectionError, DatabaseOperationError) as e:
                # Continue without user context if database issues occur
                print(f"Warning: Could not retrieve user context: {e}")

        # Get the original generator
        stream = get_business_streaming_response(
            messages=chat_message.message,
            expert_id=chat_message.expert_id,
            expert_name=expert.name,
            expert_domain=expert.domain,
            expert_perspective=expert.perspective,
            expert_style=expert.style,
            expert_context=f"Domain: {expert.domain}. Expertise: {expert.perspective}",
            user_token=chat_message.user_token,
            user_context=user_context,
            image_base64=chat_message.image_base64,
            pdf_base64=chat_message.pdf_base64,
            pdf_name=chat_message.pdf_name,
            image_name=chat_message.image_name,
        )
        
        # Wrapper to accumulate response for memory processing
        async def response_stream_wrapper():
            full_response_text = ""
            async for chunk in stream:
                full_response_text += chunk
                yield chunk
            
            # After stream finishes, trigger memory update
            if chat_message.user_token:
                conversation_pair = [
                    HumanMessage(content=chat_message.message),
                    AIMessage(content=full_response_text)
                ]
                # We can't use 'background_tasks.add_task' here effectively because 
                # the route handler has already returned. 
                # Instead, we execute the update directly (fire and forget) 
                # or rely on the fact that this runs in the generator conclusion.
                # Ideally, we should offload this to a proper background worker, 
                # but awaiting it here is acceptable for non-blocking the *stream*,
                # though it might delay the connection close slightly.
                
                # Better approach: Use FastAPI's background task system by passing it to StreamingResponse
                # BUT StreamingResponse background runs *after* the response closes.
                # So we just need to pass the data out. 
                # However, StreamingResponse background task requires a function with args.
                # We can't easily pass the dynamically generated 'full_response_text' to it 
                # because the task is defined *before* the stream runs.
                
                # PRAGMATIC SOLUTION: Run it here. It's an async operation.
                # The user has received all tokens. The browser might spin for 1 extra second
                # while we save memory, but the text is already on screen.
                try:
                    await memory_service.update_user_memory(
                        user_token=chat_message.user_token,
                        messages=conversation_pair
                    )
                except Exception as ex:
                    logging.error(f"Error in streaming memory update: {ex}")

        return StreamingResponse(response_stream_wrapper(), media_type="text/plain")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/business/experts")
async def get_business_experts():
    """Get list of available business canvas experts."""
    try:
        expert_factory = BusinessExpertFactory()
        expert_ids = expert_factory.get_available_experts()
        
        experts = []
        for expert_id in expert_ids:
            expert = expert_factory.get_expert(expert_id)
            experts.append({
                "id": expert.id,
                "name": expert.name,
                "domain": expert.domain,
                "perspective": expert.perspective,
                "style": expert.style,
            })
        
        return {"experts": experts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/business/tokens/validate")
async def validate_token(token: str = Query(...)):
    """Validate a business user token."""
    try:
        user_factory = BusinessUserFactory()
        is_valid = await user_factory.is_valid_token(token)

        if is_valid:
            user = await user_factory.get_user_by_token(token)
            if user:
                return {
                    "valid": True,
                    "role": user.role,
                    "user": {
                        "business_name": user.business_name,
                        "sector": user.sector,
                    }
                }
            else:
                return {"valid": False}
        else:
            return {"valid": False}
    except DatabaseConnectionError as e:
        # Return false for validation failures instead of 500 error
        return {"valid": False}
    except DatabaseOperationError as e:
        # Return false for validation failures instead of 500 error
        return {"valid": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---
# --- NEW: FULL CRUD ENDPOINTS FOR BUSINESS USERS ---
# ---

# --- CREATE ---
@app.post("/business/user", status_code=status.HTTP_201_CREATED)
async def create_business_user(user: BusinessUser):
    """Creates a new business user profile."""
    print(f"=== RECEIVED CREATE USER REQUEST ===")
    print(f"Request method: POST")
    print(f"Request endpoint: /business/user")
    print(f"User data received: {user.model_dump()}")
    print(f"User token: {user.token}")
    print(f"User business_name: {user.business_name}")
    
    try:
        print("Creating BusinessUserFactory instance...")
        user_factory = BusinessUserFactory()
        print("Calling user_factory.create_user()...")
        success = await user_factory.create_user(user)
        print(f"user_factory.create_user() returned: {success}")

        if success:
            print("✅ User creation successful, returning response")
            return {
                "status": "success",
                "message": f"User '{user.business_name}' created.",
                "token": user.token
            }
        else:
            print("❌ Database write operation failed silently")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database write operation failed, but no exception was raised."
            )
    except UserAlreadyExistsError as e:
        print(f"❌ UserAlreadyExistsError: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DatabaseConnectionError as e:
        print(f"❌ DatabaseConnectionError: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed. Please try again later."
        )
    except DatabaseOperationError as e:
        print(f"❌ DatabaseOperationError: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed. Please try again."
        )
    except Exception as e:
        print(f"❌ Unexpected error in create_business_user: {e}")
        print(f"Error type: {type(e)}")
        print(f"Error args: {e.args}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

# --- READ (All) ---
# REMOVED: Public endpoint exposing all users
# @app.get("/business/users", response_model=List[BusinessUser])
# async def get_all_business_users():
#     """Get a list of all business user profiles."""
#     try:
#         user_factory = BusinessUserFactory()
#         users = await user_factory.get_all_users()
#         return users
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/business/users", response_model=List[BusinessUser])
async def admin_get_all_business_users(admin_token: str = Query(...)):
    """Admin endpoint to view all business profiles"""
    user_factory = BusinessUserFactory()
    if not user_factory.validate_admin_token(admin_token):
        raise HTTPException(status_code=401, detail="Admin access required")
    
    try:
        users = await user_factory.get_all_users()
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/business/user/me", response_model=BusinessUser)
async def get_my_business_profile(token: str = Query(...)):
    """Get ONLY the business profile for the provided token"""
    user_factory = BusinessUserFactory()
    try:
        user = await user_factory.get_user_by_token(token)
        if user:
            return user
        else:
            raise HTTPException(status_code=404, detail="Profile not found")
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

# --- READ (One) ---
@app.get("/business/user/{token}", response_model=BusinessUser)
async def get_business_user(token: str):
    """Get a single business user profile by their token."""
    try:
        user_factory = BusinessUserFactory()
        user = await user_factory.get_user_by_token(token)
        if user:
            return user
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with token '{token}' not found."
            )
    except DatabaseConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed. Please try again later."
        )
    except DatabaseOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed. Please try again."
        )
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

# --- UPDATE ---
@app.put("/business/user/{token}")
async def update_business_user(token: str, user: BusinessUser):
    """Updates/Replaces a business user profile by their token."""
    try:
        user_factory = BusinessUserFactory()
        
        if token != user.token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token in URL does not match token in request body."
            )

        success = await user_factory.update_user(token, user)
        
        if success:
            return {
                "status": "success",
                "message": f"User '{user.business_name}' (token: {token}) updated."
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with token '{token}' not found. No update performed."
            )
    except DatabaseConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed. Please try again later."
        )
    except DatabaseOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed. Please try again."
        )
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

# --- DELETE ---
@app.delete("/business/user/{token}")
async def delete_business_user(token: str):
    """Deletes a business user profile by their token."""
    try:
        user_factory = BusinessUserFactory()
        success = await user_factory.delete_user(token)
        
        if success:
            return {
                "status": "success",
                "message": f"User with token '{token}' successfully deleted."
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with token '{token}' not found. No deletion performed."
            )
    except DatabaseConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed. Please try again later."
        )
    except DatabaseOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed. Please try again."
        )
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/business/user/{token}/memory")
async def reset_business_memory(token: str):
    """Resets the semantic memory (key_insights) for a business user."""
    try:
        user_factory = BusinessUserFactory()
        success = await user_factory.reset_user_memory(token)
        
        if success:
            return {
                "status": "success",
                "message": f"Memory for user '{token}' successfully reset."
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with token '{token}' not found."
            )
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
# ---
# --- END OF CRUD ENDPOINTS ---
# ---

# --- PDF EXPORT ENDPOINT ---
@app.get("/business/user/{token}/export-pdf")
async def export_bmc_pdf(token: str):
    """Export the user's Business Model Canvas as a PDF."""
    from fastapi.responses import Response
    from bmc.application.pdf_service import generate_bmc_pdf
    
    try:
        user_factory = BusinessUserFactory()
        user = await user_factory.get_user_by_token(token)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with token '{token}' not found."
            )
        
        # Generate PDF
        pdf_bytes = generate_bmc_pdf(user)
        
        # Create safe filename from business name
        safe_filename = user.business_name.replace(" ", "_").replace("/", "-")[:50]
        filename = f"{safe_filename}_BMC.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\""
            }
        )
        
    except DatabaseConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed. Please try again later."
        )
    except DatabaseOperationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed. Please try again."
        )
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logging.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
# --- END PDF EXPORT ENDPOINT ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
