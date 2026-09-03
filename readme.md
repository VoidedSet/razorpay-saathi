# Razorpay Saathi — Agentic Store

A multi-agent AI commerce platform built with FastAPI + LangGraph (backend) and Next.js (frontend).

## Stack
- **Backend:** Python, FastAPI, LangGraph, LangChain
- **Frontend:** Next.js (App Router), TypeScript
- **DB (mock):** SQLite
- **Payments:** Razorpay Payment Links + Offers API

## Getting Started

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # runs on http://localhost:3000
```

## Architecture
See [plan.md](./plan.md) for the full multi-agent design document.