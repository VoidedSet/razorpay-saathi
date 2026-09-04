# Razorpay Saathi - Backend

The backend for Razorpay Saathi is a FastAPI application that powers an intelligent, multi-agent conversational commerce experience. It uses LangGraph and LangChain to orchestrate AI agents that can assist users, answer questions, provide product recommendations, and handle checkout flows through Razorpay's API.

## Features
- **Multi-Agent Architecture**: Uses LangGraph to route intents between a conversational agent, a product search agent, and a checkout agent.
- **FastAPI**: Provides a robust and fast API for Server-Sent Events (SSE) streaming of agent responses.
- **Razorpay Integration**: Seamlessly creates payment links and fetches applicable bank offers based on user carts.
- **SQLite Database**: A lightweight database to store catalog items, cart state, and conversational history.

## Prerequisites
- Python 3.10+
- A Razorpay account with API keys.
- OpenAI API key.

## Installation

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your environment variables by copying the example file:
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` and fill in your `OPENAI_API_KEY`, `RAZORPAY_KEY_ID`, and `RAZORPAY_KEY_SECRET`.*

5. Seed the database (optional but recommended for a catalog):
   ```bash
   python generate_catalog.py
   ```

## Usage

Start the FastAPI server:
```bash
uvicorn app.main:app --reload --port 8000
```

The API will run on `http://localhost:8000`. 
- You can access the auto-generated Swagger documentation at `http://localhost:8000/docs`.
- The frontend will communicate with this server over SSE and REST endpoints.
