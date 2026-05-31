from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rag_config import FINAL_JSON_PATH


LONG_TEXT_THRESHOLD = 1800


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"未找到结构化结果文件：{path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def walk_nodes(node: Any, results: list[dict], current_chapter: str = "") -> None:
    if isinstance(node, dict):
        chapter = current_chapter

        if node.get("title"):
            chapter = str(node.get("title")).strip()

        is_clause = (
            node.get("type") == "L3"
            or (
                node.get("id")
                and node.get("content")
                and node.get("page")
            )
        )

        if is_clause:
            copied = dict(node)
            copied["_chapter"] = chapter
            results.append(copied)

        for child in node.get("sub_articles", []):
            walk_nodes(child, results, chapter)

    elif isinstance(node, list):
        for item in node:
            walk_nodes(item, results, current_chapter)


def get_text(node: dict) -> str:
    value = node.get("content") or ""
    return str(value).strip()


def get_clause_id(node: dict) -> str:
    value = node.get("id") or node.get("clause_id") or ""
    return str(value).strip()


def get_document_key(node: dict) -> str:
    value = node.get("document_id") or node.get("source") or node.get("source_path") or "unknown"
    return str(value).strip()


def get_chapter(node: dict) -> str:
    value = node.get("_chapter") or node.get("chapter") or node.get("title") or ""
    return str(value).strip()


def has_bbox(node: dict) -> bool:
    value = node.get("bbox_json") or node.get("final_bbox") or node.get("bbox")
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    return True


def build_quality_report(json_path: Path = FINAL_JSON_PATH) -> dict[str, Any]:
    data = load_json(json_path)

    nodes: list[dict] = []
    walk_nodes(data, nodes)

    clause_ids = [get_clause_id(node) for node in nodes if get_clause_id(node)]
    duplicate_clause_keys = [
        (get_document_key(node), get_clause_id(node))
        for node in nodes
        if get_clause_id(node)
    ]
    duplicate_within_document = [
        {"document_key": document_key, "clause_id": clause_id, "count": count}
        for (document_key, clause_id), count in Counter(duplicate_clause_keys).items()
        if count > 1
    ]
    duplicate_across_documents = [
        {"clause_id": clause_id, "document_count": len(document_keys)}
        for clause_id, document_keys in _documents_by_clause(nodes).items()
        if len(document_keys) > 1
    ]

    empty_text = []
    missing_page = []
    missing_bbox = []
    long_texts = []
    chapter_counter = defaultdict(int)

    for node in nodes:
        text = get_text(node)
        clause_id = get_clause_id(node)
        chapter = get_chapter(node) or "未识别章节"

        chapter_counter[chapter] += 1

        if not text:
            empty_text.append(node)
        if not node.get("page"):
            missing_page.append(node)
        if not has_bbox(node):
            missing_bbox.append(node)
        if len(text) > LONG_TEXT_THRESHOLD:
            long_texts.append(
                {
                    "clause_id": clause_id,
                    "chapter": chapter,
                    "length": len(text),
                    "preview": text[:80].replace("\n", " "),
                }
            )

    return {
        "json_path": str(json_path),
        "total_clauses": len(nodes),
        "clause_id_count": len(clause_ids),
        "duplicate_clause_id_count": len(duplicate_within_document),
        "duplicate_within_document_count": len(duplicate_within_document),
        "duplicate_across_documents_count": len(duplicate_across_documents),
        "empty_content_count": len(empty_text),
        "missing_page_count": len(missing_page),
        "missing_bbox_count": len(missing_bbox),
        "long_text_threshold": LONG_TEXT_THRESHOLD,
        "long_text_count": len(long_texts),
        "sample_duplicate_clause_ids": duplicate_within_document[:10],
        "sample_cross_document_clause_ids": duplicate_across_documents[:10],
        "sample_empty_content": [get_clause_id(node) for node in empty_text[:10]],
        "sample_missing_page": [get_clause_id(node) for node in missing_page[:10]],
        "sample_missing_bbox": [get_clause_id(node) for node in missing_bbox[:10]],
        "sample_long_texts": sorted(long_texts, key=lambda x: x["length"], reverse=True)[:10],
        "chapter_counts": dict(sorted(chapter_counter.items(), key=lambda x: x[0])),
    }


def _documents_by_clause(nodes: list[dict]) -> dict[str, set[str]]:
    documents_by_clause: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        clause_id = get_clause_id(node)
        if clause_id:
            documents_by_clause[clause_id].add(get_document_key(node))
    return documents_by_clause


def main() -> None:
    report = build_quality_report()

    print("\n========== 文档入库质量检查 ==========")
    print(f"结构化文件：{report['json_path']}")
    print(f"条文节点总数：{report['total_clauses']}")
    print(f"有条文号的节点数：{report['clause_id_count']}")
    print(f"同一文档内重复条文号数量：{report['duplicate_within_document_count']}")
    print(f"跨文档同编号条文数量：{report['duplicate_across_documents_count']}")
    print(f"空内容节点数：{report['empty_content_count']}")
    print(f"缺失 page 节点数：{report['missing_page_count']}")
    print(f"缺失 bbox 节点数：{report['missing_bbox_count']}")
    print(f"超过 {report['long_text_threshold']} 字符的长文本节点数：{report['long_text_count']}")

    print("\n========== 每章条文数量 ==========")
    for chapter, count in report["chapter_counts"].items():
        print(f"{chapter}: {count}")

    if report["sample_duplicate_clause_ids"]:
        print("\n========== 同一文档内重复条文号 Top 10 ==========")
        for item in report["sample_duplicate_clause_ids"]:
            print(item)

    if report["sample_cross_document_clause_ids"]:
        print("\n========== 跨文档同编号条文 Top 10 ==========")
        for item in report["sample_cross_document_clause_ids"]:
            print(item)

    if report["sample_long_texts"]:
        print("\n========== 长文本条文 Top 10 ==========")
        for item in report["sample_long_texts"]:
            print(f"[{item['length']} 字] {item['clause_id']} {item['chapter']} - {item['preview']}")

    print("\n检查完成")


if __name__ == "__main__":
    main()
