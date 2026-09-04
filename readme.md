# Razorpay Saathi — Agentic Store

**Razorpay Saathi** is an advanced, AI-driven conversational commerce platform that redefines how users shop online. By combining a modern web interface with a powerful multi-agent backend, it provides a tailored, interactive, and autonomous shopping experience. 

## What is it?
At its core, Razorpay Saathi is an intelligent digital salesperson. Instead of making users manually browse through thousands of products, they can simply chat with the AI. The AI agent can understand complex queries, fetch relevant products dynamically, provide personalized recommendations, apply discounts, and generate an instant Razorpay checkout link right within the chat window.

## Why build this?
Traditional e-commerce is highly manual. Users spend a lot of time filtering, searching, and comparing. Razorpay Saathi solves this by:
1. **Reducing Friction**: Users can say "I want running shoes under $100" and get instant results.
2. **Generative UI**: Instead of just text, the AI renders rich, interactive React components (like product cards and checkout widgets) in real-time based on the context.
3. **Seamless Checkout**: Leveraging Razorpay's API, the journey from discovery to payment happens in one fluid conversation.

## Project Structure
- **`/backend`**: Python, FastAPI, and LangGraph powering the AI agents and business logic.
- **`/frontend`**: Next.js and TypeScript providing the modern, responsive web application.

## How to use it

To run the full stack locally, you need to start both the backend and frontend servers.

### 1. Start the Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Be sure to add your OpenAI and Razorpay API keys!
uvicorn app.main:app --reload --port 8000
```
For more details, see the [Backend README](./backend/README.md).

### 2. Start the Frontend
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
For more details, see the [Frontend README](./frontend/README.md).

### 3. Open the App
Visit [http://localhost:3000](http://localhost:3000) in your browser to start chatting with the agent!

## Architecture
See the [plan.md](./plan.md) file for the full multi-agent technical design document.