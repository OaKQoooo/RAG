"""
Step 3: 向量入库（Chroma 版）优化版
优化点：
1. 超长文本按段落+句子拆分，避免破坏语义
2. 每章入库文档块数量统计
3. 打印最大 chunk 长度
"""

import argparse
import gc
import hashlib
import json
import os
import shutil
import re
import time
from pathlib import Path
from collections import Counter

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document

try:
    from chromadb.api.shared_system_client import SharedSystemClient
except Exception:  # pragma: no cover - Chroma internal API may vary by version
    SharedSystemClient = None

from rag_config import (
    CHROMA_DIR,
    DASHSCOPE_API_KEY,
    EMBEDDING_MODEL,
    FINAL_JSON_PATH,
    MILVUS_COLLECTION,
    ensure_runtime_dirs,
)

# --- 配置区 ---
if DASHSCOPE_API_KEY:
    os.environ["DASHSCOPE_API_KEY"] = DASHSCOPE_API_KEY

COLLECTION_NAME = MILVUS_COLLECTION
JSON_PATH = FINAL_JSON_PATH
PERSIST_DIR = CHROMA_DIR
CHUNK_SIZE = 1000   # 单条文本最大字符数


def release_chroma_clients() -> None:
    """Stop cached Chroma systems so Windows can release sqlite file locks."""
    if SharedSystemClient is not None:
        systems = list(getattr(SharedSystemClient, "_identifier_to_system", {}).values())
        for system in systems:
            try:
                system.stop()
            except Exception:
                pass
        try:
            SharedSystemClient.clear_system_cache()
        except Exception:
            pass
    gc.collect()


def reset_chroma_dir(path: Path, retries: int = 8, delay: float = 0.5) -> None:
    release_chroma_clients()
    for attempt in range(retries):
        try:
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)
            return
        except PermissionError:
            release_chroma_clients()
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def flatten_items(node: dict, items: list) -> None:
    """递归展平层级结构，提取所有叶子条款节点"""
    if "id" in node:
        items.append(node)
    for sub in node.get("sub_articles", []):
        flatten_items(sub, items)


def load_documents(json_path: str | Path) -> list[Document]:
    """将 all_docs_final.json 转换为 LangChain Document 列表"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs: list[Document] = []

    for l1 in data:
        source = l1.get("source", "Unknown")
        source_path = l1.get("source_path") or ""
        chapter = l1.get("title", "Unknown")
        document_id = l1.get("document_id")
        uploaded_by = l1.get("uploaded_by")

        items: list[dict] = []
        flatten_items(l1, items)

        for item in items:
            content = str(item.get("content", "")).strip()
            if not content:
                continue

            clause_id = str(item.get("id", "N/A"))
            page = int(item.get("page", 1))
            bbox_json = item.get("bbox_json") or json.dumps(item.get("final_bbox", []), ensure_ascii=False)
            bbox = bbox_json[:1000]

            # ==========================
            # 优化切分逻辑：先按段落拆，再按句号/分号拆
            # ==========================
            paras = re.split(r'\n{2,}', content)
            chunks = []
            for para in paras:
                para = para.strip()
                if not para:
                    continue
                if len(para) <= CHUNK_SIZE:
                    chunks.append(para)
                else:
                    # 按句号/分号拆
                    sentences = re.split(r'(?<=[。；;])', para)
                    buf = ""
                    for s in sentences:
                        s = s.strip()
                        if len(buf) + len(s) <= CHUNK_SIZE:
                            buf += s
                        else:
                            if buf:
                                chunks.append(buf)
                            buf = s
                    if buf:
                        chunks.append(buf)

            for idx, chunk in enumerate(chunks):
                cid = f"{clause_id}_p{idx}" if len(chunks) > 1 else clause_id
                docs.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "document_id": str(document_id) if document_id is not None else "",
                            "uploaded_by": str(uploaded_by) if uploaded_by is not None else "",
                            "clause_key": f"{source}::{clause_id}"[:500],
                            "source_file": source[:500],
                            "source_path": str(source_path)[:1000],
                            "clause_id": cid[:100],
                            "chapter": chapter[:500],
                            "chunk_index": idx,
                            "node_type": item.get("type", "L3"),
                            "page": page,
                            "bbox": bbox,
                            "bbox_json": bbox,
                            "page_width": item.get("page_width") or 0,
                            "page_height": item.get("page_height") or 0,
                        },
                    )
                )

    return docs


def _embeddings() -> DashScopeEmbeddings:
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("缺少 DASHSCOPE_API_KEY 环境变量，无法生成向量。")
    return DashScopeEmbeddings(
        model=EMBEDDING_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
    )


def _vector_store(collection_name: str = COLLECTION_NAME) -> Chroma:
    ensure_runtime_dirs()
    return Chroma(
        collection_name=collection_name,
        embedding_function=_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )


def delete_document(document_id: str, collection_name: str = COLLECTION_NAME) -> int:
    """Delete all vector chunks that belong to one business document."""
    vector_store = _vector_store(collection_name)
    existing = vector_store.get(where={"document_id": str(document_id)})
    ids = existing.get("ids", [])
    if ids:
        vector_store.delete(ids=ids)
    release_chroma_clients()
    return len(ids)


def replace_document(
    document_id: str,
    json_path: str | Path,
    collection_name: str = COLLECTION_NAME,
) -> int:
    """Replace one document's vector chunks without rebuilding unrelated documents."""
    docs = load_documents(json_path)
    docs = [
        doc
        for doc in docs
        if str(doc.metadata.get("document_id") or "") == str(document_id)
    ]

    if not docs:
        delete_document(document_id, collection_name)
        return 0

    ids = []
    for index, doc in enumerate(docs):
        raw_id = "|".join(
            [
                str(document_id),
                str(doc.metadata.get("clause_id") or ""),
                str(doc.metadata.get("chunk_index") or 0),
                str(doc.metadata.get("page") or 0),
                str(index),
            ]
        )
        ids.append(hashlib.sha1(raw_id.encode("utf-8")).hexdigest())

    vector_store = _vector_store(collection_name)
    existing = vector_store.get(where={"document_id": str(document_id)})
    old_ids = existing.get("ids", [])
    vector_store.add_documents(documents=docs, ids=ids)
    obsolete_ids = [item for item in old_ids if item not in ids]
    if obsolete_ids:
        vector_store.delete(ids=obsolete_ids)
    release_chroma_clients()
    return len(docs)


def ingest(
    json_path: str | Path = JSON_PATH,
    collection_name: str = COLLECTION_NAME,
    drop_old: bool = True,
) -> int:
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("缺少 DASHSCOPE_API_KEY 环境变量，无法生成向量。")

    ensure_runtime_dirs()

    json_path = Path(json_path)
    if not json_path.exists():
        print(f"错误：找不到文件 {json_path}，请先运行 step2.py")
        return 0

    if drop_old:
        reset_chroma_dir(PERSIST_DIR)

    embeddings = DashScopeEmbeddings(
        model=EMBEDDING_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
    )

    print("正在加载文档...")
    docs = load_documents(json_path)
    print(f"共加载 {len(docs)} 个文档块，开始写入 Chroma...")
    if not docs:
        return 0

    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=str(PERSIST_DIR),
    )
    _ = vector_store
    release_chroma_clients()

    # ==========================
    # 优化统计信息：每章入库文档块数量 + 最大 chunk 长度
    # ==========================
    chapter_counts = Counter(doc.metadata["chapter"] for doc in docs)
    print("\n📊 各章入库文档块数量：")
    for chap, cnt in chapter_counts.items():
        print(f"  {chap}: {cnt}")
    print(f"📦 最大 chunk 长度: {max(len(doc.page_content) for doc in docs)}")

    print(f"\n✅ Chroma 入库完成！")
    print(f"📁 向量库目录: {PERSIST_DIR}")
    print(f"📦 集合名称: {collection_name}")
    return len(docs)


def parse_args():
    parser = argparse.ArgumentParser(description="Step3 Chroma 向量化入库")
    parser.add_argument("--json", default=str(JSON_PATH), help="step2 输出 JSON")
    parser.add_argument("--collection", default=COLLECTION_NAME, help="Chroma 集合名称")
    parser.add_argument("--append", action="store_true", help="追加写入，不删除旧集合")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ingest(args.json, args.collection, drop_old=not args.append)
