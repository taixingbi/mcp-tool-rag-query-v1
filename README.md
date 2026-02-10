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

Create `.env` in the project root. Config loads `.env` then `.env.{APP_ENV}` (e.g. `.env.dev`).

```
# Required for LangChain (ChatOpenAI, OpenAIEmbeddings)
OPENAI_API_KEY=your-openai-key

# dev | qa | prod — selects which CHROMA_*_DEV / _QA / _PROD to use
APP_ENV=dev

# Chroma Cloud: use CHROMA_* or CHROMA_*_DEV / _QA / _PROD per env
CHROMA_API_KEY_DEV=...
CHROMA_TENANT_DEV=...
CHROMA_DATABASE_DEV=rag_dev
CHROMA_API_KEY_QA=...
CHROMA_TENANT_QA=...
CHROMA_DATABASE_QA=rag_qa
CHROMA_API_KEY_PROD=...
CHROMA_TENANT_PROD=...
CHROMA_DATABASE_PROD=rag_prod
```

---

## Local run (dev / qa / prod)

Set `APP_ENV` to choose which Chroma credentials (and optional `.env.qa` / `.env.prod`) are used. Default is `dev` if unset.

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

Run the container. **Required:** `OPENAI_API_KEY` and Chroma vars must be available (e.g. in `.env`). Use `--env-file .env` from the directory that contains your `.env`, or pass keys with `-e`:

```bash
docker run -p 8000:8000 \
  --env-file .env \
  -e APP_ENV=dev \
  rag-mcp
```

If you see *"api_key client option must be set"*, the container is not getting `OPENAI_API_KEY`. Ensure `.env` exists in the current directory and contains `OPENAI_API_KEY=...`, or run with:

```bash
docker run -p 8000:8000 -e OPENAI_API_KEY=your-key --env-file .env -e APP_ENV=dev rag-mcp
```


---

### Optional: sync .env to GitHub Actions secrets

One-liner (simple .env with no `#` or spaces around `=`):

```bash
gh auth login
grep -v '^#' .env | grep -v '^$' | while IFS='=' read -r name value; do gh secret set "$name" -b"$value"; done
```


