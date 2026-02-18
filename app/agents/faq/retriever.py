"""
retriever.py -- Retriever RAG para o FAQ da CT Smash.

Carrega o knowledge base (ct_smash.md), splitta por headers markdown,
gera embeddings via OpenAI e armazena em FAISS persistido em disco.

Usa lazy singleton: na 1a chamada carrega do disco (se existe) ou builda e salva.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter

_FAQ_DIR = Path(__file__).parent
_KNOWLEDGE_PATH = _FAQ_DIR / "knowledge" / "ct_smash.md"
# FAISS no Windows nao lida com Unicode em paths absolutos (ex: "João").
# Usar path relativo ao CWD para save_local/load_local.
_VECTORSTORE_DIR = _FAQ_DIR / "vectorstore"

_HEADERS_TO_SPLIT = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]

_TOP_K = 4

_vectorstore: FAISS | None = None


# Helpers internos (nao expostos fora deste módulo)
def _get_embeddings() -> OpenAIEmbeddings:
    load_dotenv()
    return OpenAIEmbeddings(model="text-embedding-3-small")


def _load_and_split():
    """Le o markdown e splitta por headers. Retorna list[Document]."""
    md_text = _KNOWLEDGE_PATH.read_text(encoding="utf-8")
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT,
        strip_headers=False,
    )
    return splitter.split_text(md_text)


def build_and_save_vectorstore() -> FAISS:
    """Builda o FAISS index do zero e salva em disco.

    Chamar quando ct_smash.md for alterado para recriar os embeddings.
    """
    docs = _load_and_split()
    embeddings = _get_embeddings()
    store = FAISS.from_documents(docs, embeddings)
    _VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
    # FAISS: usar os.path.relpath para evitar bug com Unicode em path absoluto (Windows)
    import os
    rel = os.path.relpath(str(_VECTORSTORE_DIR))
    store.save_local(rel)
    return store


def get_faq_retriever() -> FAISS:
    """Retorna o FAISS vectorstore (singleton).

    - Se a pasta vectorstore/ existe: carrega do disco (sem API call).
    - Se nao existe: builda embeddings e salva em disco.
    """
    global _vectorstore
    if _vectorstore is None:
        embeddings = _get_embeddings()
        if (_VECTORSTORE_DIR / "index.faiss").exists():
            import os
            rel = os.path.relpath(str(_VECTORSTORE_DIR))
            _vectorstore = FAISS.load_local(
                rel,
                embeddings,
                allow_dangerous_deserialization=True,
            )
        else:
            _vectorstore = build_and_save_vectorstore() # builda do zero e salva para futuras chamadas
    return _vectorstore # retorna o singleton carregado ou criado


# Funcao principal: busca os top-K chunks mais relevantes e retorna como string formatada.
def retrieve_faq_context(query: str, k: int = _TOP_K) -> str:
    """Busca os top-K chunks mais relevantes e retorna como string formatada."""
    store = get_faq_retriever()
    docs = store.similarity_search(query, k=k)
    if not docs:
        return ""
    return "\n\n".join(
        f"[Trecho {i}]\n{d.page_content}" for i, d in enumerate(docs, 1)
    )
