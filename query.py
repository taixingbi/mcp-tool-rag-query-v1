# query.py
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from config import settings, get_chroma_client

# LangSmith tags and metadata for tracing (app_version, mcp_name from settings)
def _langsmith_config(metadata: Optional[Dict[str, Any]] = None) -> dict:
    tags = []
    if settings.app_version:
        tags.append(f"app_version:{settings.app_version}")
    if settings.mcp_name:
        tags.append(f"mcp_name:{settings.mcp_name}")
    out: Dict[str, Any] = {}
    if tags:
        out["tags"] = tags
    if metadata:
        out["metadata"] = metadata
    return out

# Lazy singletons
_chroma_collection = None
_rag_chain = None
_embedder = None


def _get_chroma_collection():
    """
    Chroma Cloud collection.
    IMPORTANT: embedding_function=None means Chroma will NOT try to embed text for you.
    We always pass query_embeddings / embeddings explicitly.
    """
    global _chroma_collection
    if _chroma_collection is None:
        client = get_chroma_client()
        _chroma_collection = client.get_collection(
            name=settings.chroma_collection,
            embedding_function=None,
        )
    return _chroma_collection


def _get_embedder() -> OpenAIEmbeddings:
    global _embedder
    if _embedder is None:
        _embedder = OpenAIEmbeddings(model=settings.embedding_model)
    return _embedder


def _search_dense(
    query: str,
    k: int,
    where: Optional[Dict[str, Any]] = None,
) -> List[dict]:
    """
    Dense search (MVP):
      1) embed query using OpenAI embeddings
      2) query Chroma with query_embeddings
    """
    coll = _get_chroma_collection()
    q_emb = _get_embedder().embed_query(query)

    res = coll.query(
        query_embeddings=[q_emb],
        n_results=k,
        where=where,  # e.g. {"tenant_id": "t1"} (optional)
        include=["documents", "metadatas", "distances"],
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    out: List[dict] = []
    for i in range(len(docs)):
        meta = metas[i] or {}
        dist = float(dists[i]) if i < len(dists) and dists[i] is not None else 0.0
        out.append(
            {
                "chunk_id": meta.get("chunk_id", ""),
                "distance": dist,          # smaller = better
                "combined_score": dist,    # backward compatible name
                "dense_score": dist,       # backward compatible name
                "bm25_score": 0.0,
                "text": docs[i] or "",
                "metadata": meta,
            }
        )
    return out


class CloudRetriever(BaseRetriever):
    """
    Retriever using dense-only query embedding (MVP).
    Add `where` support later if needed.
    """
    where: Optional[Dict[str, Any]] = None  # you can set this externally

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> List[Document]:
        hits = _search_dense(query, k=settings.retrieval_k * 2, where=self.where)
        return [Document(page_content=h["text"], metadata=h["metadata"]) for h in hits]


def get_retriever(where: Optional[Dict[str, Any]] = None) -> CloudRetriever:
    r = CloudRetriever()
    r.where = where
    return r


def format_docs(docs: List[Document]) -> str:
    return "\n\n---\n\n".join(doc.page_content for doc in docs[:settings.retrieval_k])


RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You answer questions based only on the provided context. "
            "If the context does not contain relevant information, say so. "
            "Do not make up facts. Cite the context when possible.",
        ),
        ("human", "Context:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"),
    ]
)


def build_rag_chain(where: Optional[Dict[str, Any]] = None):
    """Build RAG chain. Cached after first call."""
    global _rag_chain
    if _rag_chain is None:
        _rag_chain = (
            {"context": get_retriever(where=where) | format_docs, "question": RunnablePassthrough()}
            | RAG_PROMPT
            | ChatOpenAI(
                model=settings.openai_model, 
                temperature=0,
                timeout=30,
                max_retries=2
                )
            | StrOutputParser()
        )
    return _rag_chain


def run_query(
    question: str,
    where: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    return build_rag_chain(where=where).invoke(
        question, config=_langsmith_config(metadata=metadata)
    )


# ----------------------------
# NEW: return ranked chunks + answer
# ----------------------------
def retrieve_ranked_chunks(
    question: str,
    k: int = settings.retrieval_k * 2,
    where: Optional[Dict[str, Any]] = None,
) -> List[dict]:
    """
    Return ranked chunks for debugging / UI.
    Each item includes chunk_id, distance (smaller is better), source, preview, text, metadata.
    """
    hits = _search_dense(question, k=k, where=where)

    ranked: List[dict] = []
    for h in hits:
        meta = h.get("metadata") or {}
        text = h.get("text") or ""
        ranked.append(
            {
                "chunk_id": h.get("chunk_id", "") or meta.get("chunk_id", ""),
                "distance": h.get("distance", h.get("dense_score", h.get("combined_score", 0.0))),
                "source": meta.get("source", ""),
                "preview": text[:250],
                "text": text,
                "metadata": meta,
            }
        )
    return ranked


def run_query_with_chunks(
    question: str,
    where: Optional[Dict[str, Any]] = None,
    chunk_k: int = settings.retrieval_k * 2,
) -> Dict[str, Any]:
    """
    Returns:
      {
        "answer": "...",
        "chunks": [ ... ranked chunks ... ],
        "metadata": { "reranked_chunks": [ ... ] }
      }
    """
    chunks = retrieve_ranked_chunks(question, k=chunk_k, where=where)
    answer = run_query(
        question,
        where=where,
        metadata={"reranked_chunks": chunks},
    )
    return {
        "answer": answer,
        "chunks": chunks,
        "metadata": {"reranked_chunks": chunks},
    }


if __name__ == "__main__":
    import sys
    import json

    question = input("Question: ").strip() if len(sys.argv) < 2 else " ".join(sys.argv[1:])
    if not question:
        print("Usage: python query.py <question>")
        sys.exit(1)

    result = run_query_with_chunks(question)

    print(f"Q: {question}\n")
    print(f"A: {result['answer']}\n")

    print("Top ranked chunks:\n")
    print(json.dumps(result["chunks"][:settings.retrieval_k], indent=2, ensure_ascii=False))
