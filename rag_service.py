"""FastAPI service that exposes the Python RAG pipeline to Spring Boot."""

from __future__ import annotations

import ast
import gc
import hashlib
import json
import os
import shutil
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path
from time import time
from typing import Any, NoReturn, Optional, Sequence

import chromadb
import fitz
import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_classic.retrievers.document_compressors.base import BaseDocumentCompressor
from langchain_community.chat_models import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_chroma import Chroma
from langchain_core.callbacks.manager import Callbacks
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from rag_config import STEP1_OUTPUT_DIR

import step2
import step3
from check_ingest_quality import build_quality_report, build_quality_report_for_data
from rag_config import (
    CHAT_MODEL,
    CHROMA_DIR,
    DASHSCOPE_API_KEY,
    EMBEDDING_MODEL,
    FINAL_JSON_PATH,
    MILVUS_COLLECTION,
    PDF_DIR,
    RERANK_MODEL,
    SNAPSHOT_DIR,
    SNAPSHOT_RETENTION_DAYS,
    ensure_runtime_dirs,
)
from step1 import process_single_pdf


INITIAL_RETRIEVAL_K = 15
RERANK_TOP_N = 5
RERANK_THRESHOLD = 0.05
MAX_DUPLICATE_CLAUSE_IDS = int(os.getenv("RAG_MAX_DUPLICATE_CLAUSE_IDS", "20"))
_rag_lock = threading.RLock()
_last_operation: dict[str, Any] = {
    "action": "startup",
    "status": "idle",
    "message": "服务已启动，尚未执行写操作。",
    "updated_at": None,
}
_last_snapshot_cleanup_at = 0.0


def _classify_rag_error(exc: Exception) -> tuple[str, str, int]:
    detail = str(exc)
    normalized = detail.lower()
    if any(marker in normalized for marker in ("arrearage", "overdue-payment", "account is in good standing")):
        return "MODEL_ACCOUNT_ARREARAGE", "模型服务账户状态异常，请联系管理员检查服务额度。", 503
    if any(marker in normalized for marker in ("invalid api key", "invalidapikey", "authentication", "unauthorized")):
        return "MODEL_AUTH_FAILED", "模型服务认证失败，请联系管理员检查服务配置。", 503
    if any(marker in normalized for marker in ("permission denied", "access denied", "forbidden")):
        return "MODEL_PERMISSION_DENIED", "当前模型服务权限不足，请联系管理员检查模型授权。", 503
    if any(marker in normalized for marker in ("timeout", "timed out")):
        return "MODEL_TIMEOUT", "模型服务响应超时，请稍后重试。", 504
    if any(marker in normalized for marker in ("connection refused", "connection error", "failed to establish")):
        return "MODEL_UNAVAILABLE", "模型服务暂时不可用，请稍后重试。", 503
    return "RAG_INTERNAL_ERROR", "知识库服务处理失败，请稍后重试。", 500


def _raise_rag_http_error(exc: Exception) -> NoReturn:
    error_code, message, status_code = _classify_rag_error(exc)
    raise HTTPException(
        status_code=status_code,
        detail={
            "error_code": error_code,
            "message": message,
            "detail": str(exc),
        },
    ) from exc


def _record_operation(action: str, status: str, message: str, **details: Any) -> None:
    global _last_operation
    _last_operation = {
        "action": action,
        "status": status,
        "message": message,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        **details,
    }


def cleanup_snapshot_cache(force: bool = False) -> int:
    global _last_snapshot_cleanup_at
    now = time()
    if not force and now - _last_snapshot_cleanup_at < 3600:
        return 0

    _last_snapshot_cleanup_at = now
    cutoff = now - max(0, SNAPSHOT_RETENTION_DAYS) * 24 * 60 * 60
    deleted = 0
    for path in SNAPSHOT_DIR.glob("*.png"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                deleted += 1
        except OSError:
            continue
    return deleted


SYSTEM_PROMPT = (
    "你是一个严格的水利规范检索机器人。你的回答必须遵循以下规则：\n"
    "1. 只能基于下面提供的【参考原文】进行回答，不得使用外部知识补充。\n"
    "2. 如果【参考原文】中没有包含问题的答案，直接回答："
    "'抱歉，当前规范库中未查阅到关于此问题的相关明确规定。'\n"
    "3. 如果找到了答案，回答必须包含规范名称和条款号，格式优先采用："
    "'根据《[规范名称]》第 [条款号] 条规定：[具体内容]'。\n"
    "4. 对回答中的数值、单位、时间、必须、严禁、不得等关键要求进行加粗。\n\n"
    "参考原文：\n{context}"
)

SUGGESTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一个工程规范问答系统的追问推荐助手。"
            "请基于用户问题、系统回答和参考条文，生成3个适合继续追问的问题。"
            "要求："
            "1. 每个问题必须具体、短句、可直接点击提问；"
            "2. 不要编造参考条文之外的信息；"
            "3. 不要输出解释；"
            "4. 只输出JSON数组，例如：[\"问题1\", \"问题2\", \"问题3\"]。"
        ),
        (
            "human",
            "用户问题：{question}\n\n"
            "系统回答：{answer}\n\n"
            "参考条文：\n{context}\n\n"
            "请生成3个追问问题。"
        ),
    ]
)


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatTurn] = Field(default_factory=list)
    top_k: int = Field(default=5, alias="top_k")
    enable_evidence: bool = Field(default=False, alias="enableEvidence")
    enable_suggestions: bool = Field(default=True, alias="enableSuggestions")
    user_id: Optional[Any] = Field(default=None, alias="userId")
    knowledge_scope: str = Field(default="ALL", alias="knowledgeScope")
    document_ids: list[Any] = Field(default_factory=list, alias="documentIds")
    restrict_documents: bool = Field(default=False, alias="restrictDocuments")


class ReferenceItem(BaseModel):
    source_file: str
    clause_id: str
    chapter: str = ""
    page: int = 1
    document_page: Optional[str] = None
    bbox_json: str = "[]"
    image_url: Optional[str] = None
    content_preview: str = ""
    document_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    references: list[ReferenceItem]
    suggestions: list[str]


class IngestResponse(BaseModel):
    file_name: str
    document_id: Optional[str] = None
    chunks: int
    status: str
    quality_report: Optional[dict[str, Any]] = None

class RebuildDocument(BaseModel):
    document_id: Optional[str] = None
    uploaded_by: Optional[str] = None
    file_path: str
    page_offset: Optional[int] = None


class RebuildRequest(BaseModel):
    documents: list[RebuildDocument]


class DeleteDocumentResponse(BaseModel):
    document_id: str
    deleted_chunks: int
    status: str
    quality_report: Optional[dict[str, Any]] = None


class DebugSearchRequest(BaseModel):
    question: str
    top_k: int = Field(default=10, alias="topK")
    document_ids: list[Any] = Field(default_factory=list, alias="documentIds")
    restrict_documents: bool = Field(default=False, alias="restrictDocuments")


class DashScopeReranker(BaseDocumentCompressor):
    model: str = RERANK_MODEL
    top_n: int = RERANK_TOP_N
    threshold: float = RERANK_THRESHOLD
    api_key: str = ""

    class Config:
        arbitrary_types_allowed = True

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> list[Document]:
        if not documents:
            return []

        url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "input": {"query": query, "documents": [doc.page_content for doc in documents]},
            "parameters": {"top_n": len(documents)},
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            results = resp.json()["output"]["results"]
            filtered = [r for r in results if r["relevance_score"] > self.threshold]
            if not filtered and results:
                filtered = [results[0]]
            return [
                Document(
                    page_content=documents[r["index"]].page_content,
                    metadata=documents[r["index"]].metadata,
                )
                for r in filtered[: self.top_n]
            ]
        except Exception as exc:
            print(f"Rerank 请求失败，降级为原始排序: {exc}")
            return list(documents[: self.top_n])


def _lc_history(history: list[ChatTurn]):
    messages = []
    for item in history:
        if item.role == "user":
            messages.append(HumanMessage(content=item.content))
        elif item.role == "assistant":
            messages.append(AIMessage(content=item.content))
    return messages


def _json_bbox(value) -> str:
    if value is None:
        return "[]"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _resolve_pdf_path(source_name: str, source_path: Optional[str] = None) -> Optional[Path]:
    if source_path:
        candidate = Path(source_path).expanduser()
        if candidate.exists():
            return candidate

    disk_name = source_name.replace("/", "").replace(" ", "+") + ".pdf"
    search_dirs = [PDF_DIR, Path(__file__).resolve().parent / "spring-backend" / "uploads"]
    for base_dir in search_dirs:
        pdf_path = base_dir / disk_name
        if pdf_path.exists():
            return pdf_path

    core_name = source_name.split(" ")[0].replace("/", "")
    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        for fname in os.listdir(base_dir):
            compact = fname.replace("+", "").replace(" ", "")
            if core_name and core_name in compact:
                return base_dir / fname
    return None


def build_pdf_snapshot(
    source_name: str,
    page_num,
    bbox_json: str,
    source_path: Optional[str] = None,
) -> Optional[str]:
    cleanup_snapshot_cache()
    pdf_path = _resolve_pdf_path(source_name, source_path)
    if not pdf_path:
        return None

    key = hashlib.sha1(f"{pdf_path}|{page_num}|{bbox_json}".encode("utf-8")).hexdigest()
    img_path = SNAPSHOT_DIR / f"{key}.png"
    if img_path.exists():
        return f"/snapshots/{img_path.name}"

    try:
        doc = fitz.open(pdf_path)
        page_idx = max(0, int(page_num) - 1)
        page = doc.load_page(min(page_idx, len(doc) - 1))

        if bbox_json and bbox_json != "[]":
            try:
                bbox = ast.literal_eval(bbox_json)
                rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                page.draw_rect(rect, color=(1, 0, 0), width=2, fill=(1, 0, 0), fill_opacity=0.2)
            except Exception:
                pass

        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        pix.save(img_path)
        doc.close()
        return f"/snapshots/{img_path.name}"
    except Exception as exc:
        print(f"生成原文截图失败: {exc}")
        return None


class RagEngine:
    def __init__(self) -> None:
        if not DASHSCOPE_API_KEY:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY 环境变量。")
        os.environ["DASHSCOPE_API_KEY"] = DASHSCOPE_API_KEY

        embeddings = DashScopeEmbeddings(
            model=EMBEDDING_MODEL,
            dashscope_api_key=DASHSCOPE_API_KEY,
        )
        if not CHROMA_DIR.exists():
            raise RuntimeError(f"Chroma 向量库不存在，请先上传并入库文档：{CHROMA_DIR}")

        self.vector_store = Chroma(
            collection_name=MILVUS_COLLECTION,
            embedding_function=embeddings,
            persist_directory=str(CHROMA_DIR),
        )
        self.reranker = DashScopeReranker(api_key=DASHSCOPE_API_KEY)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder("chat_history"),
                ("human", "{question}"),
            ]
        )
        llm = ChatTongyi(
            model=CHAT_MODEL,
            streaming=False,
            dashscope_api_key=DASHSCOPE_API_KEY,
        )
        self.chain = prompt | llm | StrOutputParser()
        self.suggestion_chain = SUGGESTION_PROMPT | llm | StrOutputParser()

    def format_docs(self, docs: list[Document], enable_evidence: bool = False) -> tuple[str, list[ReferenceItem]]:
        parts = []
        refs = []
        seen = set()
        for doc in docs:
            m = doc.metadata
            bbox_json = _json_bbox(m.get("bbox_json") or m.get("bbox"))
            source_file = str(m.get("source_file", ""))
            clause_id = str(m.get("clause_id", ""))
            page = int(m.get("page") or 1)
            document_page = str(m.get("document_page") or "") or None
            key = (source_file, clause_id, page, bbox_json)

            parts.append(
                f"【规范：{source_file}】\n"
                f"【章节：{m.get('chapter', '')}】\n"
                f"【条款：{clause_id}】\n"
                f"【文档页码：{document_page or page}】\n"
                f"【内容】：{doc.page_content}"
            )
            if key not in seen:
                seen.add(key)
                refs.append(
                    ReferenceItem(
                        source_file=source_file,
                        clause_id=clause_id,
                        chapter=str(m.get("chapter", "")),
                        page=page,
                        document_page=document_page,
                        bbox_json=bbox_json,
                        image_url=build_pdf_snapshot(
                            source_file,
                            page,
                            bbox_json,
                            str(m.get("source_path") or ""),
                        ) if enable_evidence else None,
                        content_preview=doc.page_content[:240],
                        document_id=str(m.get("document_id")) if m.get("document_id") is not None else None,
                    )
                )
        return "\n\n".join(parts), refs

    def suggest_questions(
        self,
        question: str,
        answer: str,
        context: str,
        refs: list[ReferenceItem],
        enabled: bool,
    ) -> list[str]:
        if not enabled:
            return []

        if not refs:
            return fallback_suggestions(refs)

        try:
            raw = self.suggestion_chain.invoke(
                {
                    "question": question,
                    "answer": answer,
                    "context": context[:4000],
                }
            )
            suggestions = parse_suggestion_output(raw)
            return suggestions or fallback_suggestions(refs)
        except Exception as exc:
            print(f"智能追问生成失败，降级为模板推荐: {exc}")
            return fallback_suggestions(refs)

    def ask(self, request: ChatRequest) -> ChatResponse:
        with _rag_lock:
            docs = self._retrieve_documents(request)[: request.top_k]
        if not docs:
            suggestions = fallback_suggestions([]) if request.enable_suggestions else []
            return ChatResponse(
                answer="抱歉，当前规范库中未查阅到关于此问题的相关明确规定。",
                references=[],
                suggestions=suggestions,
            )
        context, refs = self.format_docs(docs, enable_evidence=request.enable_evidence)
        answer = self.chain.invoke(
            {
                "context": context,
                "question": request.question,
                "chat_history": _lc_history(request.history),
            }
        )
        suggestions = self.suggest_questions(
            question=request.question,
            answer=answer,
            context=context,
            refs=refs,
            enabled=request.enable_suggestions,
        )
        return ChatResponse(answer=answer, references=refs, suggestions=suggestions)

    def debug_search(self, request: DebugSearchRequest) -> list[dict[str, Any]]:
        with _rag_lock:
            docs = self._retrieve_documents(request)
        return [
            {
                "rank": idx + 1,
                "content_preview": doc.page_content[:300],
                "metadata": doc.metadata,
            }
            for idx, doc in enumerate(docs[: request.top_k])
        ]

    def _retrieve_documents(self, request: ChatRequest | DebugSearchRequest) -> list[Document]:
        search_filter = None
        allowed_ids: set[str] = set()
        if request.restrict_documents:
            allowed_ids = {str(item) for item in request.document_ids if item is not None}
            if not allowed_ids:
                return []
            search_filter = (
                {"document_id": next(iter(allowed_ids))}
                if len(allowed_ids) == 1
                else {"document_id": {"$in": sorted(allowed_ids)}}
            )

        docs = self.vector_store.similarity_search(
            request.question,
            k=INITIAL_RETRIEVAL_K,
            filter=search_filter,
        )
        docs = self.reranker.compress_documents(docs, request.question)
        if not request.restrict_documents:
            return docs

        # Keep a defensive check even though Chroma already applies the filter.
        allowed_ids = {str(item) for item in request.document_ids if item is not None}
        return [
            doc
            for doc in docs
            if str(doc.metadata.get("document_id") or "") in allowed_ids
        ]


def parse_suggestion_output(text: str) -> list[str]:
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()][:3]
    except Exception:
        pass

    lines = []
    for line in text.splitlines():
        clean = line.strip()
        clean = clean.lstrip("-0123456789.、)） ").strip()
        if clean:
            lines.append(clean)
    return lines[:3]

def fallback_suggestions(refs: list[ReferenceItem]) -> list[str]:
    if not refs:
        return ["是否需要换一种问法重新检索？"]
    first = refs[0]
    return [
        f"{first.clause_id} 条款的适用条件是什么？",
        f"{first.source_file} 中还有哪些相关规定？",
        "请把这些条款整理成审查要点。",
    ]


ensure_runtime_dirs()
cleanup_snapshot_cache(force=True)
app = FastAPI(title="Dam Standard RAG Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/snapshots", StaticFiles(directory=str(SNAPSHOT_DIR)), name="snapshots")

_engine: Optional[RagEngine] = None


def get_engine() -> RagEngine:
    global _engine
    with _rag_lock:
        if _engine is None:
            _engine = RagEngine()
        return _engine


def _read_structured_dataset() -> list[dict]:
    if not FINAL_JSON_PATH.exists():
        return []
    with FINAL_JSON_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, list) else []


def _write_structured_dataset(items: list[dict]) -> None:
    FINAL_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="rag-dataset-",
            dir=str(FINAL_JSON_PATH.parent),
            encoding="utf-8",
            delete=False,
        ) as temp_file:
            json.dump(items, temp_file, ensure_ascii=False, indent=2)
            temp_path = Path(temp_file.name)
        os.replace(temp_path, FINAL_JSON_PATH)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _without_structured_document(items: list[dict], document_id: str) -> list[dict]:
    return [
        item
        for item in items
        if str(item.get("document_id") or "") != str(document_id)
    ]


def _structured_document(items: list[dict], document_id: str) -> list[dict]:
    return [
        item
        for item in items
        if str(item.get("document_id") or "") == str(document_id)
    ]


def _delete_pdf_sources(items: list[dict]) -> None:
    for item in items:
        source_path = Path(str(item.get("source_path") or "")).resolve()
        if source_path.is_file() and source_path.parent == PDF_DIR.resolve():
            source_path.unlink(missing_ok=True)


def _validate_structured_document(document_id: str, items: list[dict], previous_dataset: list[dict]) -> dict[str, Any]:
    document_report = build_quality_report_for_data(items)
    clause_count = document_report["total_clauses"]
    duplicate_count = document_report["duplicate_within_document_count"]
    if clause_count == 0:
        raise ValueError(f"文档 {document_id} 未解析出任何条款，已拒绝覆盖原向量")
    if duplicate_count > MAX_DUPLICATE_CLAUSE_IDS:
        raise ValueError(
            f"文档 {document_id} 存在 {duplicate_count} 组重复条款编号，"
            f"超过允许阈值 {MAX_DUPLICATE_CLAUSE_IDS}，已拒绝入库"
        )
    candidate_dataset = [*_without_structured_document(previous_dataset, document_id), *items]
    return build_quality_report_for_data(candidate_dataset, FINAL_JSON_PATH)


def _replace_document_vectors(document_id: str, structured_items: list[dict]) -> int:
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="rag-incremental-",
            dir=str(SNAPSHOT_DIR),
            encoding="utf-8",
            delete=False,
        ) as temp_file:
            json.dump(structured_items, temp_file, ensure_ascii=False, indent=2)
            temp_path = Path(temp_file.name)
        return step3.replace_document(document_id, temp_path)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


def _structured_document_ids(items: list[dict]) -> set[str]:
    return {
        str(item.get("document_id"))
        for item in items
        if item.get("document_id") is not None
    }


def _vector_store_status() -> dict[str, Any]:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        collection = client.get_collection(MILVUS_COLLECTION)
    except Exception:
        return {
            "collection_exists": False,
            "actual_chunks": 0,
            "document_ids": [],
        }

    payload = collection.get(include=["metadatas"])
    metadata = payload.get("metadatas") or []
    document_ids = sorted({
        str(item.get("document_id"))
        for item in metadata
        if item and item.get("document_id") not in (None, "")
    })
    return {
        "collection_exists": True,
        "actual_chunks": collection.count(),
        "document_ids": document_ids,
    }


def _build_operational_status() -> dict[str, Any]:
    warnings = []
    items = _read_structured_dataset()
    quality = build_quality_report_for_data(items, FINAL_JSON_PATH)
    structured_ids = _structured_document_ids(items)
    expected_chunks = len(step3.load_documents(FINAL_JSON_PATH)) if FINAL_JSON_PATH.exists() else 0

    vector_status = _vector_store_status()
    vector_ids = set(vector_status["document_ids"])
    actual_chunks = vector_status["actual_chunks"]
    orphan_vector_ids = sorted(vector_ids - structured_ids)
    missing_vector_ids = sorted(structured_ids - vector_ids)

    if not DASHSCOPE_API_KEY:
        warnings.append("未配置 DashScope API Key")
    if not vector_status["collection_exists"]:
        warnings.append("Chroma 集合尚未创建")
    if expected_chunks != actual_chunks:
        warnings.append(f"向量块数量不一致：预期 {expected_chunks}，实际 {actual_chunks}")
    if orphan_vector_ids:
        warnings.append(f"存在 {len(orphan_vector_ids)} 个残留向量文档")
    if missing_vector_ids:
        warnings.append(f"存在 {len(missing_vector_ids)} 个缺失向量文档")

    return {
        "status": "ok" if not warnings else "warning",
        "service": "Dam Standard RAG Service",
        "vector_store": "chroma",
        "collection": MILVUS_COLLECTION,
        "dashscope_configured": bool(DASHSCOPE_API_KEY),
        "structured_clauses": quality["total_clauses"],
        "structured_documents": len(structured_ids),
        "expected_chunks": expected_chunks,
        "actual_chunks": actual_chunks,
        "consistent": expected_chunks == actual_chunks and not orphan_vector_ids and not missing_vector_ids,
        "orphan_vector_document_ids": orphan_vector_ids,
        "missing_vector_document_ids": missing_vector_ids,
        "warnings": warnings,
        "last_operation": _last_operation,
    }


@app.get("/health")
def health():
    try:
        with _rag_lock:
            return _build_operational_status()
    except Exception as exc:
        return {
            "status": "error",
            "service": "Dam Standard RAG Service",
            "vector_store": "chroma",
            "collection": MILVUS_COLLECTION,
            "dashscope_configured": bool(DASHSCOPE_API_KEY),
            "consistent": False,
            "warnings": [str(exc)],
            "last_operation": _last_operation,
        }


@app.get("/")
def root():
    return {
        "service": "Dam Standard RAG Service",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/api/rag/quality")
def quality_report():
    try:
        with _rag_lock:
            return build_quality_report()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/rag/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        return get_engine().ask(request)
    except Exception as exc:
        _raise_rag_http_error(exc)


@app.post("/api/rag/debug/search")
def debug_search(request: DebugSearchRequest):
    try:
        return {
            "question": request.question,
            "results": get_engine().debug_search(request),
        }
    except Exception as exc:
        _raise_rag_http_error(exc)


@app.post("/api/rag/documents/ingest", response_model=IngestResponse)
def ingest_document(
    file: UploadFile = File(...),
    document_id: Optional[str] = Form(default=None),
    uploaded_by: Optional[str] = Form(default=None),
    page_offset: Optional[int] = Form(default=None),
    append: bool = Form(default=False),
):
    file_name = Path(file.filename or "").name
    if not file_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    try:
        global _engine
        if not document_id:
            raise ValueError("document_id is required for incremental ingest")
        with _rag_lock:
            _record_operation("ingest", "running", f"正在入库文档 {document_id}", document_id=document_id)
            _engine = None
            gc.collect()
            dest = PDF_DIR / file_name
            with open(dest, "wb") as out:
                shutil.copyfileobj(file.file, out)

            previous_dataset = _read_structured_dataset()
            step1_path = process_single_pdf(
                dest,
                document_id=document_id,
                uploaded_by=uploaded_by,
                page_offset=page_offset,
            )
            structured_items = step2.parse_step1_json(Path(step1_path))
            quality_report = _validate_structured_document(document_id, structured_items, previous_dataset)
            candidate_dataset = [*_without_structured_document(previous_dataset, document_id), *structured_items]
            _write_structured_dataset(candidate_dataset)
            try:
                chunks = _replace_document_vectors(document_id, structured_items)
            except Exception:
                _write_structured_dataset(previous_dataset)
                raise
            _engine = None
            _record_operation(
                "ingest",
                "completed",
                f"文档 {document_id} 入库完成",
                document_id=document_id,
                chunks=chunks,
            )
        return IngestResponse(
            file_name=file_name,
            document_id=document_id,
            chunks=chunks,
            status="completed",
            quality_report=quality_report,
        )
    except Exception as exc:
        _record_operation("ingest", "failed", str(exc), document_id=document_id)
        traceback.print_exc()
        _raise_rag_http_error(exc)


@app.delete("/api/rag/documents/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(document_id: str):
    global _engine
    try:
        with _rag_lock:
            _record_operation("delete", "running", f"正在删除文档 {document_id}", document_id=document_id)
            _engine = None
            gc.collect()
            previous_dataset = _read_structured_dataset()
            removed_items = _structured_document(previous_dataset, document_id)
            remaining_items = _without_structured_document(previous_dataset, document_id)
            deleted_chunks = step3.delete_document(document_id)
            try:
                _write_structured_dataset(remaining_items)
            except Exception:
                if removed_items:
                    _replace_document_vectors(document_id, removed_items)
                raise
            _delete_pdf_sources(removed_items)
            quality_report = build_quality_report_for_data(remaining_items, FINAL_JSON_PATH)
            _engine = None
            _record_operation(
                "delete",
                "completed",
                f"文档 {document_id} 已删除",
                document_id=document_id,
                deleted_chunks=deleted_chunks,
            )
        return DeleteDocumentResponse(
            document_id=document_id,
            deleted_chunks=deleted_chunks,
            status="completed",
            quality_report=quality_report,
        )
    except Exception as exc:
        _record_operation("delete", "failed", str(exc), document_id=document_id)
        traceback.print_exc()
        _raise_rag_http_error(exc)


@app.post("/api/rag/documents/rebuild", response_model=IngestResponse)
def rebuild_documents(request: RebuildRequest):
    global _engine
    structured_temp_path: Optional[Path] = None
    try:
        with _rag_lock:
            _record_operation("rebuild", "running", "正在全量重建知识库")
            _engine = None
            gc.collect()

            if STEP1_OUTPUT_DIR.exists():
                shutil.rmtree(STEP1_OUTPUT_DIR)
            STEP1_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            for doc in request.documents:
                pdf_path = Path(doc.file_path)
                if not pdf_path.exists():
                    raise FileNotFoundError(f"PDF not found: {pdf_path}")
                process_single_pdf(
                    pdf_path,
                    output_folder=STEP1_OUTPUT_DIR,
                    document_id=doc.document_id,
                    uploaded_by=doc.uploaded_by,
                    page_offset=doc.page_offset,
                )

            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                prefix="rag-rebuild-",
                dir=str(SNAPSHOT_DIR),
                encoding="utf-8",
                delete=False,
            ) as temp_file:
                structured_temp_path = Path(temp_file.name)
            structured_items = step2.build_structured_dataset(
                input_folder=STEP1_OUTPUT_DIR,
                output_file=structured_temp_path,
            )
            quality_report = build_quality_report_for_data(structured_items, FINAL_JSON_PATH)
            if quality_report["total_clauses"] == 0 and request.documents:
                raise ValueError("全量重建未解析出任何条款，已中止向量写入")
            if quality_report["duplicate_within_document_count"] > MAX_DUPLICATE_CLAUSE_IDS:
                raise ValueError(
                    "全量重建发现 "
                    f"{quality_report['duplicate_within_document_count']} 组同文档重复条款编号，"
                    f"超过允许阈值 {MAX_DUPLICATE_CLAUSE_IDS}，已中止向量写入"
                )
            chunks = step3.ingest(json_path=structured_temp_path, drop_old=True)
            _write_structured_dataset(structured_items)

            _engine = None
            _record_operation("rebuild", "completed", "知识库全量重建完成", chunks=chunks)
        return IngestResponse(
            file_name="rebuild",
            document_id=None,
            chunks=chunks,
            status="completed",
            quality_report=quality_report,
        )
    except Exception as exc:
        _record_operation("rebuild", "failed", str(exc))
        traceback.print_exc()
        _raise_rag_http_error(exc)
    finally:
        if structured_temp_path:
            structured_temp_path.unlink(missing_ok=True)
