# OmniRAG

The PDF document assistant uses a FastAPI backend and a React frontend built with Vite.

See [backend/README.md](backend/README.md) for configuration, running the application, API endpoints, validation and operating limits.

Build the frontend once, then start FastAPI from this directory (Node.js 20.19+ or 22.12+ required):

```powershell
cd frontend
npm.cmd install
npm.cmd run build
cd ..
backend/.venv/Scripts/python.exe -m uvicorn omnirag.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000. Set your Gemini API key in `backend/.env`, upload a PDF, index it and ask a question.

For frontend development, keep FastAPI running and run `npm.cmd run dev` from `frontend/`. Open http://127.0.0.1:5173; Vite proxies API requests to port 8000. See [frontend/README.md](frontend/README.md).
