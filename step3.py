"""
Step 3: 向量入库 (LangChain 版)

流程：读取 step2 输出的 all_docs_final.json
      → 构建 LangChain Document 对象
      → DashScopeEmbeddings 生成稠密向量
      → 分批写入 Milvus 向量数据库
"""

import argparse
import json
import os
import time
from pathlib import Path

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Milvus
from langchain_core.documents import Document

from rag_config import (
    DASHSCOPE_API_KEY,
    EMBEDDING_MODEL,
    FINAL_JSON_PATH,
    MILVUS_COLLECTION,
    MILVUS_HOST,
    MILVUS_PORT,
)

# --- 配置区 ---
if DASHSCOPE_API_KEY:
    os.environ["DASHSCOPE_API_KEY"] = DASHSCOPE_API_KEY

COLLECTION_NAME = MILVUS_COLLECTION
JSON_PATH = FINAL_JSON_PATH
CHUNK_SIZE = 8000   # 单条文本最大字符数
BATCH_SIZE = 25     # 每批向量化的文档数（控制 DashScope QPS）


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
                            "document_id": document_id,
                            "clause_key": f"{source}::{clause_id}"[:500],
                            "source_file": source[:500],
                            "clause_id": cid[:100],
                            "chapter": chapter[:500],
                            "chunk_index": idx,
                            "node_type": item.get("type", "L3"),
                            "page": page,
                            "bbox": bbox,
                            "bbox_json": bbox,
                            "page_width": item.get("page_width"),
                            "page_height": item.get("page_height"),
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

    json_path = Path(json_path)
    if not json_path.exists():
        print(f"错误：找不到文件 {JSON_PATH}，请先运行 step2.py")
        return 0

    # 初始化 DashScope 嵌入模型
    embeddings = DashScopeEmbeddings(
        model=EMBEDDING_MODEL,
        dashscope_api_key=DASHSCOPE_API_KEY,
    )

    print("正在加载文档...")
    docs = load_documents(json_path)
    print(f"共加载 {len(docs)} 个文档块，开始分批写入 Milvus...")
    if not docs:
        return 0

    connection_args = {"host": MILVUS_HOST, "port": MILVUS_PORT}

    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        drop_for_batch = drop_old and i == 0  # 首批创建集合，后续批次追加

        Milvus.from_documents(
            documents=batch,
            embedding=embeddings,
            connection_args=connection_args,
            collection_name=collection_name,
            drop_old=drop_for_batch,
            text_field="content",
        )

        done = min(i + BATCH_SIZE, len(docs))
        pct = done * 100 // len(docs)
        print(f"  进度: {done}/{len(docs)} ({pct}%)")

        if i + BATCH_SIZE < len(docs):
            time.sleep(1)  # QPS 保护

    print(f"\n✅ 入库完成！集合名称: {collection_name}")
    return len(docs)


def parse_args():
    parser = argparse.ArgumentParser(description="Step3 向量化入库")
    parser.add_argument("--json", default=str(JSON_PATH), help="step2 输出 JSON")
    parser.add_argument("--collection", default=COLLECTION_NAME, help="Milvus 集合名称")
    parser.add_argument("--append", action="store_true", help="追加写入，不删除旧集合")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ingest(args.json, args.collection, drop_old=not args.append)
