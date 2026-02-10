# RAG Pipeline

Hybrid search (BM25 + dense) over documents with Chroma Cloud and LangChain.

## Setup

```bash
python3.11 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env`:

```
OPENAI_API_KEY=your-openai-key
# dev | qa | prod — run_query and MCP use this to pick Chroma + vector_store
APP_ENV=dev

# Per-environment Chroma (config reads CHROMA_*_DEV / _QA / _PROD)
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

## Local run (dev / qa / prod)

The app uses `APP_ENV` to choose Chroma credentials and local paths (`vector_store/<env>`, BM25 under that). Default is `dev` if unset.


### One-liner (simple .env with no # or spaces around =):
```bash
gh auth login
grep -v '^#' .env | grep -v '^$' | while IFS='=' read -r name value; do gh secret set "$name" -b"$value"; done
```

```bash
APP_ENV=dev  python query.py "what is taixing visa"
APP_ENV=qa  python query.py "what is taixing visa"
APP_ENV=prod  python query.py "what is taixing visa"
```

```bash
APP_ENV=dev uvicorn mcp_server:app --reload
APP_ENV=qa uvicorn mcp_server:app --reload
APP_ENV=prod uvicorn mcp_server:app --reload

curl http://127.0.0.1:8000/health

```





