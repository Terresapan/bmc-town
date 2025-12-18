# Project Overview

This project is a course on building AI agents called "BMC Town". It consists of a Python backend (`bmc-api`) and a JavaScript-based game UI (`bmc-ui`).

The backend is a **FastAPI** application that leverages **LangGraph** to orchestrate stateful, multimodal agent workflows. It uses **Google's Gemini** models for generation and **LangSmith** for observability and evaluation.
The frontend is a web-based game built with the **Phaser** game framework, allowing users to interact with "Business Experts" in a virtual world.

The project uses **Docker** to manage the local infrastructure and connects to a cloud-hosted **MongoDB Atlas** database for persisting business user profiles.

# Architecture

## Backend (`bmc-api`)
- **Framework**: FastAPI
- **Orchestration**: LangGraph
- **LLM Provider**: Google Gemini (requires `GEMINI_API_KEY`)
- **Agent Model**: "Business Experts"
  - Agents are hardcoded personas (defined in `BusinessExpertFactory`) mapped to the Business Model Canvas (e.g., Value Proposition, Customer Segments).
  - **Workflow**: The agent logic is implemented as a graph:
    1.  **Input**: Text + Optional Images/PDFs.
    2.  **File Processing**: Multimodal inputs are processed and attached to the context.
    3.  **Conversation**: The model generates a response based on the expert's persona and user context.
    4.  **Summarization**: The conversation state is updated.
- **Security**:
  - **Role-Based Access Control (RBAC)**: Distinguishes between standard users and admins.
  - **File Isolation**: Uploaded files (Images/PDFs) are isolated to the user's current session token and are not shared between users.

## Frontend (`bmc-ui`)
- **Framework**: Phaser 3 (Game) + DOM Elements (UI)
- **Communication**: `ApiService.js` handles REST calls to the backend.
- **Features**:
  - **Smart Login**: Token-based authentication for users; password-based for admins.
  - **Multimodal Chat**: Users can upload images and PDFs which are sent to the backend as Base64 strings.

## Evaluation (`bmc-api/evals`)
The project includes a comprehensive evaluation suite using **LangSmith** and **Google Gemini** as a judge.

-   **Rule-Based Evaluator**: Fast, deterministic checks for:
    -   Conciseness (Word count < 50)
    -   Identity Safety (Ensuring the agent doesn't say "As an AI...")
    -   File Integrity (Verifying file payloads if claimed)
-   **LLM Judge (Gemini)**: A slower, deep semantic check that:
    -   Uploads the user's context files (PDF/Image) to Google's File API.
    -   Asks Gemini 2.5 Flash to verify if the agent's response is factually supported by the provided documents.
    -   Detects hallucinations by strictly checking cited facts against the file content.

# Building and Running

The project uses a top-level `Makefile` to orchestrate the build and run process.

**Prerequisites:**
- Ensure you have a `bmc-api/.env` file containing:
  - `MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/...`
  - `ADMIN_TOKEN=test-admin-token` (or your preferred secure token for admin API access)
  - `GEMINI_API_KEY=AIza...` (Required for Google Gemini models)
  - `LANGSMITH_API_KEY=lsv2...` (Required for tracing and evaluation)

**1. Start the application:**

To start the application stack (backend and frontend), run the following command from the root directory:

```bash
make infrastructure-up
```

This will start:
- `bmc-api`: Backend API at `http://localhost:8000`
- `bmc-ui`: Frontend Game at `http://localhost:8080`

**2. Stop the application:**

```bash
make infrastructure-stop
```

**3. Run Evaluations:**

To evaluate the latest runs logged to LangSmith:

```bash
make evaluate-runs
```

This command executes `bmc-api/evals/run_evals.py`, which pulls the last 10 runs from the "Business Model Canvas" project in LangSmith and runs both Rule-Based and LLM Judge evaluations.

**4. API Endpoints:**

The following key endpoints are exposed by the backend:

-   `POST /chat/business`: Main chat endpoint for Business Experts. Supports multimodal input.
-   `POST /chat/business/stream`: Streaming version of the chat endpoint.
-   `POST /business/user`: Create a new business user profile.
-   `GET /business/user/me`: Get the current user's profile.
-   `GET /business/experts`: List available Business Experts.
-   `DELETE /business/user/{token}/memory`: Reset the semantic memory for a user.

# Development Conventions

## Backend

The backend is a Python project using `uv`.

```bash
cd bmc-api
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

## Frontend

The frontend is a JavaScript project using `npm`.

```bash
cd bmc-ui
npm install
npm run dev # Development mode
npm run build # Production build
```

# Legacy / Deprecated

-   **Philosopher Agents**: The original "Philosopher" agents (Turing, Aristotle) and their associated endpoints (`/chat`) appear to be deprecated in favor of the Business Expert system.
-   **Offline Pipelines**: The `call-agent`, `create-long-term-memory`, and related commands in the `Makefile` are currently **disabled** and commented out. They rely on a legacy `tools` module that is pending refactoring. They will be restored in a future update.

# Feature: Long-Term Memory (Shared Living Context)

This feature implements a "Shared Living Context" that persists stateful business knowledge across different Business Expert sessions.

## 1. Core Concept: "Background Fact-Checker"
A background process running on **Gemini 2.5 Flash Lite** that extracts business insights after every meaningful interaction. This ensures that:
1.  Insights are captured immediately (Real-time).
2.  The user's response is not delayed (Non-blocking / Background Task).
3.  Memory is persistent across Expert switches.

## 2. Architecture & Data Flow

### A. Memory Schema (`BusinessInsights`)
-   **Location**: Embedded in `BusinessUser` collection in MongoDB.
-   **Structure**: 4-part Semantic Memory:
    1.  **Canvas State**: The 9 BMC Blocks (e.g., `customer_segments`, `value_propositions`).
    2.  **Constraints**: Boundaries (e.g., "No subscription models").
    3.  **Preferences**: User interaction style (e.g., "Prefers bullet points").
    4.  **Pending Topics**: Working memory for next steps.

### B. Writing Strategy (The "Fact-Checker")
-   **Service**: `bmc-api/src/philoagents/application/memory_service.py`
-   **Trigger**: Attached to `/chat/business` and `/chat/business/stream` as a FastAPI `BackgroundTask`.
-   **Logic**:
    1.  User sends message -> Agent responds -> API returns response.
    2.  **Background Task**: `MemoryService.update_user_memory`
    3.  **LLM Call**: Gemini Flash Lite analyzes the last turn + existing memory.
    4.  **Prompt**: "Extract explicit agreed facts. Resolve conflicts (User wins). Format as JSON."
    5.  **Observability**: Runs are tagged with `memory_extraction` and include `user_token` metadata in LangSmith.
    6.  **Persistence**: Updates `BusinessUser` in MongoDB if changes are detected.

### C. Reading Strategy (Context Injection)
-   **Mechanism**: `BusinessUser.to_context_string()`
-   **Logic**:
    1.  When a chat starts, `BusinessUser` is loaded.
    2.  `to_context_string()` formats the `key_insights` into a readable "SHARED LIVING CONTEXT" block.
    3.  This block is injected into the System Prompt (`BUSINESS_EXPERT_CHARACTER_CARD`).

## 3. User Transparency & Control (Remember, Update, Forget)
The application prioritizes user agency over their data through three explicit mechanisms:

### A. Remember (View)
-   **What**: Users can see exactly what the system has "learned" about them and their business.
-   **Where**: **Main Menu -> Edit Profile**.
-   **Mechanism**: The "Profile Dashboard" fetches the `BusinessUser` object (via `GET /business/user/me`) and populates the form fields with the current persistent state.

### B. Update (Edit)
-   **What**: Users can manually correct or refine the AI's memory (e.g., fixing a constraint or changing a preference).
-   **Where**: **Main Menu -> Edit Profile**.
-   **Mechanism**: Submitting the form calls `PUT /business/user`, directly updating the `BusinessUser` document in MongoDB. This allows "human-in-the-loop" correction of the AI's long-term memory.

### C. Forget (Delete)
-   **What**: Users can wipe the slate clean, removing all learned "Shared Living Context" while keeping their basic account metadata.
-   **Where**: **Game Scene -> Pause Menu (ESC Key) -> Reset Game**.
-   **Mechanism**:
    1.  User confirms the destructive action.
    2.  Frontend calls `DELETE /business/user/{token}/memory`.
    3.  Backend executes `reset_user_memory`, clearing the `key_insights` sub-document.
    4.  Game reloads to ensure a fresh state.

## 4. Implementation Status
-   ✅ **Schema**: Added `BusinessInsights` to `BusinessUser`.
-   ✅ **Service**: Implemented `MemoryService` with Gemini Flash Lite.
-   ✅ **Integration**: Connected to FastAPI BackgroundTasks (Stream & Standard).
-   ✅ **Observability**: Added Tags and Metadata for LangSmith filtering.
-   ✅ **UI - View/Edit**: "Edit Profile" form in Main Menu.
-   ✅ **UI - Forget**: "Reset Game" button in Pause Menu.

# Lesson Learned: Search Integration

We explored multiple architectures to enable "Active Research" capabilities for the agents. Here is a summary of the attempts and the final working solution.

### Failed Attempts (The "Valley of Death")
*   **Native Grounding via LangChain:** Failed due to type validation errors (`Unsupported tool type`) and version mismatches between `langchain-google-genai` and `google-genai` SDK.
*   **Open Source Scrapers:** `googlesearch-python` and `duckduckgo-search` proved unreliable in Docker due to aggressive IP blocking by search providers.
*   **Standard Tool Loop (Tavily):** While successful, it introduced a paid dependency (`tavily-python`) which was suboptimal for a free/educational project.

### Solution: Native Gemini SDK Integration (The "Holy Grail")
We successfully implemented a **Hybrid Architecture** where the core conversation node bypasses LangChain wrappers and communicates directly with the **Google GenAI SDK**.

*   **Approach:** `business_conversation_node` now instantiates a native `google.genai.Client`.
*   **Search:** We enable Native Grounding by passing `tools=[{'google_search': {}}]` directly to the API. This provides **Free, High-Quality Search** without extra dependencies.
*   **Multimodal:** We use native `types.Part(inline_data=...)` to handle PDF and Image attachments, mirroring the previous capability.
*   **Tracing:** We manually wrapped the SDK call with `@traceable` to ensure visibility in LangSmith.
*   **Outcome:** A robust, free, and fully functional search agent that maintains the clean structure of the LangGraph workflow.

**Key Takeaway:**
When library wrappers (like LangChain) lag behind native SDK features (like Gemini's Grounding), "ejecting" to the native SDK for specific nodes is a powerful and valid architectural pattern. It restores control and unlocks the full potential of the underlying model.