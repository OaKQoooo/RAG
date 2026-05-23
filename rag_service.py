"""FastAPI service that exposes the Python RAG pipeline to Spring Boot."""

from __future__ import annotations

import ast
import gc
import hashlib
import json
import os
import shutil
import traceback
from pathlib import Path
from typing import Any, Optional, Sequence

import fitz
import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_classic.retrievers import ContextualCompressionRetriever
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
from rag_config import (
    CHAT_MODEL,
    CHROMA_DIR,
    DASHSCOPE_API_KEY,
    EMBEDDING_MODEL,
    MILVUS_COLLECTION,
    PDF_DIR,
    RERANK_MODEL,
    SNAPSHOT_DIR,
    ensure_runtime_dirs,
)
from step1 import process_single_pdf


INITIAL_RETRIEVAL_K = 15
RERANK_TOP_N = 5
RERANK_THRESHOLD = 0.05


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

class RebuildDocument(BaseModel):
    document_id: Optional[str] = None
    uploaded_by: Optional[str] = None
    file_path: str


class RebuildRequest(BaseModel):
    documents: list[RebuildDocument]


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


def _resolve_pdf_path(source_name: str) -> Optional[Path]:
    disk_name = source_name.replace("/", "").replace(" ", "+") + ".pdf"
    pdf_path = PDF_DIR / disk_name
    if pdf_path.exists():
        return pdf_path

    core_name = source_name.split(" ")[0].replace("/", "")
    if PDF_DIR.exists():
        for fname in os.listdir(PDF_DIR):
            compact = fname.replace("+", "").replace(" ", "")
            if core_name and core_name in compact:
                return PDF_DIR / fname
    return None


def build_pdf_snapshot(source_name: str, page_num, bbox_json: str) -> Optional[str]:
    pdf_path = _resolve_pdf_path(source_name)
    if not pdf_path:
        return None

    key = hashlib.sha1(f"{source_name}|{page_num}|{bbox_json}".encode("utf-8")).hexdigest()
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

        vector_store = Chroma(
            collection_name=MILVUS_COLLECTION,
            embedding_function=embeddings,
            persist_directory=str(CHROMA_DIR),
        )
        base_retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": INITIAL_RETRIEVAL_K},
        )
        self.retriever = ContextualCompressionRetriever(
            base_compressor=DashScopeReranker(api_key=DASHSCOPE_API_KEY),
            base_retriever=base_retriever,
        )
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
            key = (source_file, clause_id, page, bbox_json)

            parts.append(
                f"【规范：{source_file}】\n"
                f"【章节：{m.get('chapter', '')}】\n"
                f"【条款：{clause_id}】\n"
                f"【页码：{page}】\n"
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
                        bbox_json=bbox_json,
                        image_url=build_pdf_snapshot(source_file, page, bbox_json) if enable_evidence else None,
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
        docs = self._filter_documents(self.retriever.invoke(request.question), request)[: request.top_k]
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

    def _filter_documents(self, docs: list[Document], request: ChatRequest) -> list[Document]:
        if not request.restrict_documents:
            return docs
        allowed_ids = {str(item) for item in request.document_ids if item is not None}
        if not allowed_ids:
            return []
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
    if _engine is None:
        _engine = RagEngine()
    return _engine


@app.get("/health")
def health():
    return {
        "status": "ok",
        "vector_store": "chroma",
        "collection": MILVUS_COLLECTION,
        "pdf_dir": str(PDF_DIR),
        "chroma_dir": str(CHROMA_DIR),
        "chroma_exists": CHROMA_DIR.exists(),
        "dashscope_configured": bool(DASHSCOPE_API_KEY),
    }


@app.get("/")
def root():
    return {
        "service": "Dam Standard RAG Service",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
    }


@app.post("/api/rag/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        return get_engine().ask(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/rag/documents/ingest", response_model=IngestResponse)
def ingest_document(
    file: UploadFile = File(...),
    document_id: Optional[str] = Form(default=None),
    uploaded_by: Optional[str] = Form(default=None),
    append: bool = Form(default=False),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    dest = PDF_DIR / file.filename
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        global _engine
        _engine = None
        gc.collect()
        process_single_pdf(dest, document_id=document_id, uploaded_by=uploaded_by)
        step2.build_structured_dataset()
        chunks = step3.ingest(drop_old=not append)
        _engine = None
        return IngestResponse(
            file_name=file.filename,
            document_id=document_id,
            chunks=chunks,
            status="completed",
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/rag/documents/rebuild", response_model=IngestResponse)
def rebuild_documents(request: RebuildRequest):
    global _engine
    try:
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
            )

        step2.build_structured_dataset(input_folder=STEP1_OUTPUT_DIR)
        chunks = step3.ingest(drop_old=True)

        _engine = None
        return IngestResponse(
            file_name="rebuild",
            document_id=None,
            chunks=chunks,
            status="completed",
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc