"""
domains/_shared/rag_store.py
獨立的知識庫向量資料庫，跟晨報的 infra/status_store.py 完全分開——這裡存
的是一般性的知識文件（例如你的 Obsidian 筆記）。

之後法規知識庫、可轉債知識庫如果要各自建立獨立的 collection，就是在這支
檔案的基礎上，讓呼叫端傳入不同的 collection_name / persist_directory，
不用重寫一份新的向量檢索邏輯。

用的是本機 Chroma，資料存在一個資料夾裡，不用另外架服務。Embedding
模型跟著 config.LLM_PROVIDER 走，邏輯跟 orchestrator/langchain_agent.py
的 _build_llm() 一樣，只是換成 embedding 版本。

需要安裝：
    pip install langchain-chroma chromadb langchain-text-splitters
"""
import os

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import infra.config as config
from infra.paths import PROJECT_ROOT

# 可選：如果你想指定別的路徑/collection 名稱，在 config.py 加這兩個變數
# 覆蓋掉即可；沒加的話就用這裡的預設值。
KB_PERSIST_DIR = getattr(
    config, "KB_PERSIST_DIR",
    os.path.join(PROJECT_ROOT, "kb_store"),
)
KB_COLLECTION_NAME = getattr(config, "KB_COLLECTION_NAME", "knowledge_base")

_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)


def _build_embeddings():
    """
    跟 orchestrator/langchain_agent.py 的 _build_llm() 邏輯對應，只是換
    成 embedding 模型。三個 provider 的 embedding 模型名稱可以在
    config.py 加對應的 *_EMBEDDING_MODEL 覆蓋，沒加就用這裡的預設值。

    注意：如果用 ollama，這個 embedding 模型要另外 pull 一次：
        ollama pull nomic-embed-text
    """

    # if config.LLM_PROVIDER == "openai":
    #     from langchain_openai import OpenAIEmbeddings
    #     model = getattr(config, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    #     return OpenAIEmbeddings(
    #         model=model, api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL,
    #     )
    if config.LLM_PROVIDER == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        model = getattr(config, "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
        return GoogleGenerativeAIEmbeddings(model=model, google_api_key=config.GEMINI_API_KEY)
    from langchain_ollama import OllamaEmbeddings
    model = getattr(config, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    return OllamaEmbeddings(model=model, base_url=config.OLLAMA_HOST)


def _get_vectorstore():
    from langchain_chroma import Chroma
    return Chroma(
        collection_name=KB_COLLECTION_NAME,
        embedding_function=_build_embeddings(),
        persist_directory=KB_PERSIST_DIR,
    )


def add_document(text: str, metadata: dict) -> int:
    """把一份文件（原始全文）切塊後加進知識庫，回傳切了幾個片段。
    metadata 建議至少帶 source（檔名或路徑），之後檢索到才知道是從
    哪一份文件來的。
    """
    text = (text or "").strip()
    if not text:
        return 0
    chunks = _splitter.split_text(text)
    docs = [Document(page_content=chunk, metadata=metadata) for chunk in chunks]
    _get_vectorstore().add_documents(docs)
    return len(docs)


def search(query: str, k: int = 5) -> list:
    """語意檢索，回傳最相關的 k 個片段，每個是
    {"content": ..., "metadata": ..., "score": ...}（score 越小越相關）。
    """
    results = _get_vectorstore().similarity_search_with_score(query, k=k)
    return [
        {"content": doc.page_content, "metadata": doc.metadata, "score": score}
        for doc, score in results
    ]


def count_documents() -> int:
    """知識庫目前有多少個片段，用來確認索引有沒有跑成功。"""
    try:
        return _get_vectorstore()._collection.count()
    except Exception:
        return 0
