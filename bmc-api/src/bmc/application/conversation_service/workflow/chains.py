from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory
from google.genai import Client

from bmc.config import settings
from bmc.domain.prompts import (
    BUSINESS_EXPERT_CHARACTER_CARD,
    EXTEND_SUMMARY_PROMPT,
    SUMMARY_PROMPT,
)


def get_chat_model(temperature: float = 0.7, model_name: str = settings.GEMINI_LLM_MODEL) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        api_key=settings.GEMINI_API_KEY,
        model=model_name, # type: ignore
        temperature=temperature,
        safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    },
)

def get_native_client() -> Client:
    """Returns a configured native Google GenAI SDK Client."""
    return Client(api_key=settings.GEMINI_API_KEY)


def get_business_expert_response_chain():
    """
    Chain for business canvas expert conversations.
    Binds the Search tool for real-time information.
    """
    # 1. Get the model
    model = get_chat_model()
    
    # 2. Bind the Search tool
    # We use .bind_tools() for standard LangChain tools.
    # This allows the model to choose to call the tool.
    model_with_tools = model.bind_tools([SEARCH_TOOL])

    system_message = BUSINESS_EXPERT_CHARACTER_CARD

    # 3. Create the prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message.prompt),
            MessagesPlaceholder(variable_name="messages"),
        ],
        template_format="jinja2",
    )

    # 4. Construct the chain
    # We return the chain. The output will be an AIMessage.
    # If the model uses the tool, it will contain tool_calls.
    return prompt | model_with_tools


def get_business_conversation_summary_chain(summary: str = ""):
    """Summary chain for business expert conversations."""
    model = get_chat_model(model_name=settings.GEMINI_LLM_MODEL_CONTEXT_SUMMARY) # type: ignore

    summary_message = EXTEND_SUMMARY_PROMPT if summary else SUMMARY_PROMPT

    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="messages"),
            ("human", summary_message.prompt),
        ],
        template_format="jinja2",
    )

    return prompt | model
