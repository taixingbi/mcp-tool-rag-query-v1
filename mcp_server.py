# mcp_server.py — MCP server using tools registered in query.py
import contextlib
from fastapi import FastAPI
from mcp.server import FastMCP

from config import settings
from query import register_mcp_tools

# Use mcp.server.FastMCP so we can run session_manager in parent lifespan when mounted.
# streamable_http_path="/" so the sub-app route matches when mounted at /mcp (path becomes / or "").
mcp = FastMCP(
    settings.mcp_name,
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)

# Register RAG tools from query.py
register_mcp_tools(mcp)

mcp_app = mcp.streamable_http_app()


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="mcp_tool_rag_query_v1", version="0.1.0", lifespan=_lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "mcp": settings.mcp_name}


app.mount("/mcp", mcp_app)
