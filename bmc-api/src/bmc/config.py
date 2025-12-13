from pathlib import Path
import os
import logging

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logger for this module
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore", 
        env_file_encoding="utf-8",
        case_sensitive=True  # Ensure ENV reads from environment
    )
    
    # --- Environment ---
    # This will read from ENV environment variable, or fall back to detecting Cloud Run
    ENV: str = Field(default="local")

    # --- GEMINI Configuration ---
    GEMINI_API_KEY: str
    GEMINI_LLM_MODEL: str = "gemini-2.5-flash-lite"
    GEMINI_LLM_MODEL_CONTEXT_SUMMARY: str = "gemini-2.5-flash-lite"
    GEMINI_LLM_MODEL_EVALUATION: str = "gemini-2.5-flash"

    # --- LangSmith Configuration ---
    LANGSMITH_API_KEY: str | None = Field(default=None)
    LANGSMITH_TRACING: bool = True
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_PROJECT: str = "Business Model Canvas"


    # --- MongoDB Configuration ---
    MONGODB_URI: str 
    MONGODB_DB_NAME: str = "bmc"
    MONGODB_DB_DEV_NAME: str = "bmc_dev"
    MONGODB_USER_COLLECTION: str = "business_users"
    MONGO_STATE_CHECKPOINT_COLLECTION: str = "checkpoints"
    MONGO_STATE_WRITES_COLLECTION: str = "checkpoint_writes"

    @model_validator(mode='after')
    def configure_environment(self):
        # Auto-detect Cloud Run if ENV not explicitly set to production
        if self.ENV == "local" and "K_SERVICE" in os.environ:
            self.ENV = "production"
            logger.info("🔧 Detected Cloud Run (K_SERVICE present), switching ENV to 'production'")
        
        # Set database name based on environment
        if self.ENV == "local":
            self.MONGODB_DB_NAME = self.MONGODB_DB_DEV_NAME
            logger.info(f"🔧 ENV is 'local', using dev database: {self.MONGODB_DB_NAME}")
        else:
            self.MONGODB_DB_NAME = "bmc"
            logger.info(f"🔧 ENV is '{self.ENV}', using production database: {self.MONGODB_DB_NAME}")
        
        return self

    # --- Agents Configuration ---
    TOTAL_MESSAGES_SUMMARY_TRIGGER: int = 14
    TOTAL_MESSAGES_AFTER_SUMMARY: int = 5

    # --- Paths Configuration ---
    # EVALUATION_DATASET_FILE_PATH: Path = Path("data/evaluation_dataset.json")
    # EXTRACTION_METADATA_FILE_PATH: Path = Path("data/extraction_metadata.json")


settings = Settings() # type: ignore

# --- Export Settings to Environment Variables for LangChain Tracing ---
# LangChain libraries rely on environment variables for tracing configuration.
if settings.LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.LANGSMITH_TRACING else "false"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    
    # Ensure compatibility with different SDK versions
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_TRACING"] = "true" if settings.LANGSMITH_TRACING else "false"
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT


logger.info(f"🔧 CONFIG LOADED: ENV={settings.ENV}")
logger.info(f"🔧 CONFIG LOADED: DB_NAME={settings.MONGODB_DB_NAME}")
logger.info(f"🔧 CONFIG LOADED: LANGSMITH_PROJECT={settings.LANGSMITH_PROJECT}")
