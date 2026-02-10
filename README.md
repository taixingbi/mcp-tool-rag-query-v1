# RAG Pipeline

RAG over documents using **Chroma Cloud** (dense search) and **LangChain**. Exposes tools via **MCP** (Model Context Protocol) so clients can call `rag_query` and `rag_query_with_chunks` over HTTP.

---

## Setup

Create a virtualenv and install dependencies:

```bash
python3.11 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install --upgrade pip
pip install -r requirements.txt
```

Create env files in the project root. Config loads `.env` then `.env.{APP_ENV}` (e.g. `APP_ENV=qa` → `.env` then `.env.qa`). Use the same variable names in each file; values differ per env.

**`.env`** (dev or shared):

```
APP_VERSION=v:1.01
OPENAI_API_KEY=your-openai-key
CHROMA_API_KEY=...
CHROMA_TENANT=...
CHROMA_DATABASE=rag_dev
```

**`.env.qa`** and **`.env.prod`** — same keys, qa/prod values (e.g. `CHROMA_DATABASE=rag_qa` or `rag_prod`). Set `APP_ENV=qa` or `APP_ENV=prod` when running so the right file is loaded.

---

## Local run (dev / qa / prod)

Set `APP_ENV` so config loads `.env` then `.env.{APP_ENV}` (e.g. `APP_ENV=qa` → `.env.qa`). Default is `dev`.

### Run RAG from the CLI (no server)

```bash
APP_ENV=dev  python query.py "what is taixing visa"
APP_ENV=qa   python query.py "what is taixing visa"
APP_ENV=prod python query.py "what is taixing visa"
```

### Run the MCP HTTP server

Start the server (optional: set `APP_ENV` for Chroma env):

```bash
APP_ENV=dev  uvicorn mcp_server:app --reload --port 8000
APP_ENV=qa   uvicorn mcp_server:app --reload --port 8000
APP_ENV=prod uvicorn mcp_server:app --reload --port 8000
```

### Health check

```bash
curl http://127.0.0.1:8000/health
```

### Call MCP tools via curl

Use **trailing slash** (`/mcp/`) to avoid 307 redirect.

**`rag_query`** — returns only the RAG answer (plain text):

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rag_query","arguments":{"question":"what is Taixing visa?"}},"id":1}' \
  http://localhost:8000/mcp/
```

**`rag_query_with_chunks`** — returns answer + ranked chunks as JSON:

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rag_query_with_chunks","arguments":{"question":"what is Taixing visa?"}},"id":1}' \
  http://localhost:8000/mcp/
```


### Docker

Build the image:

```bash
docker build -t rag-mcp .
```

Run the container. Pass env from the correct file for the env you want (`.env` / `.env.qa` / `.env.prod`). The image does not include env files (they are in `.dockerignore`).

```bash
# dev (from directory that has .env)
docker run -p 8000:8000 --env-file .env -e APP_ENV=dev rag-mcp

# qa
docker run -p 8000:8000 --env-file .env.qa -e APP_ENV=qa rag-mcp

# prod
docker run -p 8000:8000 --env-file .env.prod -e APP_ENV=prod rag-mcp
```

If you see *"api_key client option must be set"*, the container is not getting `OPENAI_API_KEY`. Use `--env-file .env` (or `.env.qa` / `.env.prod`) from the directory that contains that file, or pass `-e OPENAI_API_KEY=...`.


---

## Optional: sync env to GitHub Actions secrets

One-liner (simple .env with no `#` or spaces around `=`):

```bash
gh auth login
grep -v '^#' .env | grep -v '^$' | while IFS='=' read -r name value; do gh secret set "$name" -b"$value"; done
```


