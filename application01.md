# Business Model Canvas Town

**Business Model Canvas Town** is an innovative, gamified platform designed to transform the dry, traditional process of business modeling into an engaging, interactive experience. By combining a charming pixel-art RPG world with advanced AI agents, it enables entrepreneurs, students, and strategists to build robust business models intuitively.

## Business Goals

The primary goal of Business Model Canvas Town is to **democratize business strategy**.
-   **Increase Engagement**: Replace static templates with a living, breathing world.
-   **Enhance Learning**: Use conversational AI to guide users through complex concepts.
-   **Accelerate Strategy**: Help users generate and refine business ideas faster through structured expert guidance.

## Target User Personas

1.  **The Aspiring Entrepreneur**: Has a great idea but struggles with the formal structure of a business plan. Needs guidance and examples.
2.  **The Business Student**: Learning the ropes of strategy. Needs an engaging way to practice concepts without getting bored by textbooks.
3.  **The Corporate Strategist**: Needs a fresh perspective and a structured way to brainstorm new product lines or pivots with a team.
4.  **Consulting Firms**:  Want to enhance and scale their client services. By pre-loading client profiles, consultants can offer a tailored, AI-driven experience that automates initial strategy sessions and provides consistent, high-quality advice.

## Features

### 1. Interactive Town Environment
-   **Immersive World**: Explore a beautifully crafted pixel-art town.
-   **Exploration**: Walk around, find buildings, and discover experts.
-   **Dynamic Movement**: Realistic character movement and collision detection powered by Phaser 3.

### 2. Personalized Agent Intelligence
One of the application's most powerful features is **deep customization**. 
-   **Pre-built Context**: Admins or consultants can pre-load a user's profile, including their **name**, **business challenges**, and **strategic goals**.
-   **Context-Aware Interactions**: When a user begins a session, the agent already knows who they are and what they are trying to achieve. The agent will **address the user by name** and tailor advice to their specific challenges, creating a seamless and highly personalized consulting experience.

### 3. The Business Experts (AI Agents)
The core of the experience. Nine specialized AI agents, each representing a building block of the Business Model Canvas, reside in the town. They don't just chat; they **consult**.

*   **Steven Segments (Customer Segments)**: Analytical market researcher. Helps identify target nuances.
*   **Victor Value (Value Propositions)**: Creative problem-solver. Focuses on the "why" and "what".
*   **Chloe Channels (Channels)**: Strategic distribution expert. Plans how to reach customers.
*   **Rita Relations (Customer Relationships)**: Warm relationship specialist. Designs retention and loyalty strategies.
*   **Ryan Revenue (Revenue Streams)**: Numbers-oriented financial strategist. Maximizes income potential.
*   **Rebecca Resources (Key Resources)**: Practical operations expert. Identifies essential assets.
*   **Alex Activities (Key Activities)**: Efficiency-minded process specialist. Defines core workflows.
*   **Parker Partners (Key Partnerships)**: Network-savvy business developer. Connects with suppliers and allies.
*   **Carlos Costs (Cost Structure)**: Pragmatic financial analyst. detailed breakdown of expenses.

### 3. Multimodal Intelligence
-   **Smart Context**: Users can upload **PDFs and Images** (e.g., market reports, product sketches).
-   **Visual Analysis**: Agents can "see" uploaded diagrams and read documents to provide context-aware advice.

**Example Queries:**
> *   "Here is a PDF of my competitor's annual report. Based on their weaknesses, what unique value proposition should I focus on?"
> *   "I've uploaded a sketch of my new product design. Which customer segments would be most interested in this form factor?"
> *   "Review this chart of my current revenue streams. Are there any obvious monetization opportunities I am missing?"

### 5. Smart Login & Security
-   **Secure Access**: Token-based authentication for users.
-   **Data Isolation**: User data and uploaded files are strictly isolated per session.

## System Architecture

The application is built on a modern, scalable stack designed for performance and intelligence.

### User Interface (Frontend)
-   **Framework**: **Phaser 3** (Game Engine) embedded within a responsive web application.
-   **Language**: JavaScript.
-   **Communication**: RESTful API calls via `ApiService.js`.

### Backend Services (API)
-   **Framework**: **FastAPI** (Python). High-performance, async-ready.
-   **Orchestration**: **LangGraph**. Manages the complex state and workflow of agent conversations.
-   **LLM Provider**: **Google Gemini**. Powers the cognitive abilities of the Business Experts.
-   **Database**: **MongoDB Atlas**. Stores user profiles and game state in the cloud.
-   **Infrastructure**: Docker-containerized for easy deployment to platforms like Google Cloud Run.

## Evaluation & Quality Assurance

To ensure the advice given by experts is high-quality and safe, the system employs a rigorous evaluation pipeline (`bmc-api/evals`).

1.  **Rule-Based Evaluation (Fast)**
    -   Checks for conciseness (preventing rambling).
    -   Ensures identity consistency (agents never break character or say "As an AI...").
    -   Verifies file integrity.

2.  **LLM Judge (Deep Semantic Check)**
    -   Powered by **Google Gemini 2.5 Flash**.
    -   **Fact-Checking**: Uploads user context files to the model to strictly verify that agent responses are factually supported by the provided documents.
    -   **Hallucination Detection**: penalizes any advice not grounded in the user's provided context or established business theory.
    -   **Observability**: All runs are traced and logged via **LangSmith** for continuous improvement.
