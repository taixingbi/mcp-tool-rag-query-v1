# MCP Streamable HTTP cURL Examples

Start the server first: `uvicorn mcp_server:app --reload --port 8000`

Base URL: `http://localhost:8000/mcp/` (use trailing slash to avoid 307 redirect)

This server runs in **stateless** mode: no session ID is required. You can call tools directly.

## Stateless: call rag_query (no session)

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rag_query","arguments":{"question":"what is Taixing visa?"}},"id":1}' \
  http://localhost:8000/mcp/
```

If your question contains a single quote (e.g. "Taixing's"), escape it in the shell: use `'\''` for one literal quote, or put the JSON in a file and use `-d @request.json`.




curl -s -X POST http://localhost:8000/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":"q-1","method":"tools/call","params":{"name":"rag_query","arguments":{"question":"what is taixing visa"}}}'
