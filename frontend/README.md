# OmniRAG React frontend

React components manage the document library, upload and indexing operations, document selection, search/chat conversation, and source citations. Vite bundles React locally; the application does not depend on a CDN runtime.

The workspace fills the viewport. Conversation history scrolls independently above a stationary question composer; the library has its own scroll area. On phones, the library opens from the header. Enter sends a question and Shift+Enter adds a line. The Ask button stays disabled until the selected scope contains a ready document. Scroll upward to inspect earlier answers without automatically jumping to the latest answer.

The interface uses a blue, slate and white palette. Source excerpts are collapsed by default under **View evidence**; activate the down arrow with a click or keyboard to expand or collapse them. Each excerpt links to the original PDF page. Legacy excerpts that start mid-word are expanded from saved source text when their offsets can be verified; no missing text is invented.

Use Node.js 20.19+ or 22.12+.

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Run FastAPI separately on port 8000 and open http://127.0.0.1:5173. Vite proxies `/api`, `/docs`, `/openapi.json`, and `/health` to the backend so no CORS configuration is needed.

For a production build:

```powershell
npm.cmd run build
```

FastAPI serves `frontend/dist/index.html` at `/` and the compiled assets at `/assets`. Rebuild after source changes. On systems without PowerShell's npm script restriction, `npm` works in place of `npm.cmd`.

Source files:

- `src/App.jsx`: application state and library, conversation and citation components.
- `src/api.js`: shared API request and error handling.
- `src/main.jsx`: React root and stylesheet import.
- `style.css`: responsive workspace design.
- `vite.config.js`: development API proxy.
