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

from config import CHAT_MODEL, RETRIEVAL_K, EMBEDDING_MODEL, CHROMA_SETTINGS, get_chroma_client

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
            name=CHROMA_SETTINGS["collection_name"],
            embedding_function=None,
        )
    return _chroma_collection


def _get_embedder() -> OpenAIEmbeddings:
    global _embedder
    if _embedder is None:
        _embedder = OpenAIEmbeddings(model=EMBEDDING_MODEL)
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
        hits = _search_dense(query, k=RETRIEVAL_K * 2, where=self.where)
        return [Document(page_content=h["text"], metadata=h["metadata"]) for h in hits]


def get_retriever(where: Optional[Dict[str, Any]] = None) -> CloudRetriever:
    r = CloudRetriever()
    r.where = where
    return r


def format_docs(docs: List[Document]) -> str:
    return "\n\n---\n\n".join(doc.page_content for doc in docs[:RETRIEVAL_K])


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
                model=CHAT_MODEL, 
                temperature=0,
                timeout=30,
                max_retries=2
                )
            | StrOutputParser()
        )
    return _rag_chain


def run_query(question: str, where: Optional[Dict[str, Any]] = None) -> str:
    return build_rag_chain(where=where).invoke(question)


# ----------------------------
# NEW: return ranked chunks + answer
# ----------------------------
def retrieve_ranked_chunks(
    question: str,
    k: int = RETRIEVAL_K * 2,
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
    chunk_k: int = RETRIEVAL_K * 2,
) -> Dict[str, Any]:
    """
    Returns:
      {
        "answer": "...",
        "chunks": [ ... ranked chunks ... ]
      }
    """
    chunks = retrieve_ranked_chunks(question, k=chunk_k, where=where)
    answer = run_query(question, where=where)
    return {"answer": answer, "chunks": chunks}


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
    print(json.dumps(result["chunks"][:RETRIEVAL_K], indent=2, ensure_ascii=False))
