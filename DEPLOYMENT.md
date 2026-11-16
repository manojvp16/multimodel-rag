# Deploy OmniRAG on Render

This deployment runs React and FastAPI together in one Docker container. Qdrant runs in embedded mode. Uploaded PDFs, evidence, metadata and vectors share a persistent disk. One shared username/password protects the workspace, including PDFs, API docs and API requests. This is a private single-user deployment, not a multi-user application with isolated accounts.

## Included deployment files

| File | Responsibility |
| --- | --- |
| `Dockerfile` | Build React with Node 22, install locked Python dependencies and English Tesseract OCR, serve on the platform's `PORT` |
| `.dockerignore` | Keep local credentials, uploads, virtual environments and caches out of the image build context |
| `render.yaml` | Create one paid Docker service with a 1 GB persistent disk and prompt for runtime secrets |
| `compose.deploy.yaml` | Test the production container locally with a persistent Docker volume |
| `.env.deploy.example` | Template for local container settings; contains no real credentials |
| `scripts/package_deploy.py` | Export a clean source archive with frontend and backend together |

## 1. Publish the complete source to GitHub

Run from the OmniRAG project root:

```powershell
backend/.venv/Scripts/python.exe scripts/package_deploy.py
```

Extract `dist/omnirag-deploy.zip` into a **new, empty folder** outside this checkout, then create a new private GitHub repository and push the extracted folder. Do not include the zip itself in the repository. Your current nested `backend/.git` does not cover the frontend or root deployment files; the archive includes both directories as ordinary source folders and leaves your existing repository untouched.

From the extracted folder, substitute your new GitHub repository URL:

```powershell
git init
git add .
git commit -m "Prepare OmniRAG deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Check that GitHub shows `Dockerfile`, `render.yaml`, `frontend/` and `backend/` at the repository root. No real `.env` files or personal PDFs should appear. This archive does not migrate local uploaded documents; upload and index them on the deployed site.

## 2. Optional local container verification

Start Docker Desktop with Linux containers. From the project root:

```powershell
Copy-Item .env.deploy.example .env.deploy
```

Edit `.env.deploy`: set your real Gemini key, your currently working chat model, a username, and a unique password of at least 16 characters. Do not leave the example password. Then run:

```powershell
docker compose -f compose.deploy.yaml up --build -d
docker compose -f compose.deploy.yaml logs -f
```

Open http://127.0.0.1:8000 and enter the username/password in the browser sign-in prompt. If your development backend is using port 8000, stop it first. `/health` is accessible without signing in for platform health checks. This endpoint verifies application liveness, not Gemini connectivity.

Test upload → Index → ask → expand evidence → open PDF → restart the service and confirm documents still exist:

```powershell
docker compose -f compose.deploy.yaml restart
```

Stop with `docker compose -f compose.deploy.yaml down`. Avoid `down -v` because it removes the persistent volume and stored documents.

## 3. Create the Render Blueprint

1. Sign in at https://dashboard.render.com and choose **New → Blueprint**.
2. Connect the new GitHub repository. Keep the service root at the repository root, not `backend/`.
3. Render reads `render.yaml`. Review the paid `starter` service and persistent disk before creating resources; hosting and Gemini API usage are billed separately.
4. Supply the prompted secret values:

| Variable | Value |
| --- | --- |
| `GEMINI_API_KEY` | Your Gemini API key, entered directly in Render |
| `GEMINI_CHAT_MODEL` | The exact model name currently working in your local `backend/.env` |
| `AUTH_USERNAME` | Your chosen workspace username |
| `AUTH_PASSWORD` | A unique password of at least 16 characters |

The Blueprint sets `DEBUG=false`, `QDRANT_LOCAL=true`, `EMBEDDING_DIMENSIONS=768`, `GEMINI_EMBEDDING_MODEL=gemini-embedding-2`, and `STORAGE_DIR=/app/backend/storage`. If your working local embedding settings differ, change the Blueprint values to match before deployment. Do not put real secret values in GitHub or `render.yaml`.

5. Create the Blueprint. Docker builds the frontend and Python environment, then starts Uvicorn on `0.0.0.0:$PORT` with exactly one worker. Use the default Docker command; no separate build or start command is needed.
6. When Render reports the service live, open its **HTTPS** URL, sign in, upload a PDF, click **Index**, and ask a question.

The persistent disk mount is `/app/backend/storage`, exactly matching `STORAGE_DIR`. Render's ephemeral filesystem would otherwise lose uploads and vectors on restart. Embedded Qdrant requires one process, and Render's disk is attached to one service instance. Do not increase Uvicorn workers or instance count.

## 4. Verify and maintain

- Open `/health`; it should return HTTP 200. Sign-in protection should return HTTP 401 for unauthenticated API requests.
- Confirm a PDF can be uploaded, indexed, searched, answered with expandable evidence, and opened from its citation.
- Restart the Render service and check that the document list and indexed state survive.
- Delete a test document and confirm it disappears from retrieval.
- Use the Render logs and displayed error reference to diagnose provider failures. Quota/rate limits require waiting or reviewing your Gemini account.
- Changing embedding models/dimensions requires reindexing. Update environment variables in Render and redeploy when changing keys, passwords or model configuration.
- Everyone with the shared login sees the same library and can delete its documents. Use HTTPS for this deployment. Basic authentication has a browser-managed sign-in prompt rather than an application logout button.
- Back up documents and metadata outside the container. For a consistent full storage backup, stop application writes and copy the entire storage directory, including Qdrant files. Keep backups outside the service's disk. Redeployments with a persistent disk can briefly interrupt the service.

## Common deployment failures

| Symptom | Action |
| --- | --- |
| `Production requires AUTH_USERNAME and AUTH_PASSWORD` | Set both secrets in Render and redeploy |
| Password or API-key validation failure | Replace placeholder values; use a password with at least 16 characters |
| Port not detected | Keep the supplied Docker command and the platform's `PORT` |
| Missing React page/assets | Check the frontend build log and that the whole project was pushed |
| Documents disappear after restart | Verify the persistent disk is mounted at `/app/backend/storage` |
| Qdrant storage already accessed | Run one worker and one service instance |
| Provider access/model error | Check the runtime Gemini key and exact supported model name |
| Rate-limit/quota error | Wait or adjust the Gemini account's quota/billing; redeploying will not reset it |

This repository prepares deployment; creating a Blueprint and obtaining a live URL happen in your Render account. A successful local source build alone does not verify cloud deployment.

References: [Render Docker](https://render.com/docs/docker), [Blueprint specification](https://render.com/docs/blueprint-spec), [persistent disks](https://render.com/docs/disks), [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/).
