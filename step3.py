"""
Step 3: 向量入库（Chroma 版）

流程：读取 step2 输出的 all_docs_final.json
      → 构建 LangChain Document 对象
      → DashScopeEmbeddings 生成稠密向量
      → 写入本地 Chroma 向量数据库
"""

import argparse
import json
import os
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document

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

            # 超长文本按 CHUNK_SIZE 切块
            chunks = [content[i:i + CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]
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

    if drop_old and PERSIST_DIR.exists():
        shutil.rmtree(PERSIST_DIR)
        PERSIST_DIR.mkdir(parents=True, exist_ok=True)

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
