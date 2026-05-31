"""Shared configuration for the RAG pipeline and HTTP service."""

from __future__ import annotations

import os
from pathlib import Path


CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

PDF_DIR = _path_from_env("RAG_PDF_DIR", PROJECT_ROOT / "Dam_Docs")
STEP1_OUTPUT_DIR = _path_from_env("RAG_STEP1_OUTPUT_DIR", CODE_DIR / "step1_outputs")
FINAL_JSON_PATH = _path_from_env("RAG_FINAL_JSON_PATH", CODE_DIR / "all_docs_final.json")
SNAPSHOT_DIR = _path_from_env("RAG_SNAPSHOT_DIR", CODE_DIR / "runtime" / "snapshots")
CHROMA_DIR = _path_from_env("RAG_CHROMA_DIR", CODE_DIR / "runtime" / "chroma_db")

MILVUS_HOST = os.getenv("MILVUS_HOST", "127.0.0.1")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "dam_expert_db")

EMBEDDING_MODEL = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v2")
CHAT_MODEL = os.getenv("DASHSCOPE_CHAT_MODEL", "qwen-max")
RERANK_MODEL = os.getenv("DASHSCOPE_RERANK_MODEL", "gte-rerank-v2")
SNAPSHOT_RETENTION_DAYS = int(os.getenv("RAG_SNAPSHOT_RETENTION_DAYS", "7"))


def ensure_runtime_dirs() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    STEP1_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
