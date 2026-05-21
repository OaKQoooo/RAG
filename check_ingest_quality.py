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

        # 顶层章节一般有 title，例如 "1 总 则"
        if node.get("title"):
            chapter = str(node.get("title")).strip()

        # 当前项目中，真正条款节点通常是 type=L3，并且有 id/content/page
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

        # 递归 sub_articles
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


def main() -> None:
    data = load_json(FINAL_JSON_PATH)

    nodes: list[dict] = []
    walk_nodes(data, nodes)

    clause_ids = [get_clause_id(node) for node in nodes if get_clause_id(node)]
    duplicate_ids = [item for item, count in Counter(clause_ids).items() if count > 1]

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

    print("\n========== 文档入库质量检查 ==========")
    print(f"结构化文件：{FINAL_JSON_PATH}")
    print(f"条款节点总数：{len(nodes)}")
    print(f"有条款号的节点数：{len(clause_ids)}")
    print(f"重复条款号数量：{len(duplicate_ids)}")
    print(f"空内容节点数：{len(empty_text)}")
    print(f"缺失 page 节点数：{len(missing_page)}")
    print(f"缺失 bbox 节点数：{len(missing_bbox)}")
    print(f"超过 {LONG_TEXT_THRESHOLD} 字符的长文本节点数：{len(long_texts)}")

    print("\n========== 每章条款数量 ==========")
    for chapter, count in sorted(chapter_counter.items(), key=lambda x: x[0]):
        print(f"{chapter}: {count}")

    if duplicate_ids:
        print("\n========== 重复条款号 Top 20 ==========")
        for item in duplicate_ids[:20]:
            print(item)

    if long_texts:
        print("\n========== 长文本条款 Top 10 ==========")
        for item in sorted(long_texts, key=lambda x: x["length"], reverse=True)[:10]:
            print(f"[{item['length']} 字] {item['clause_id']} {item['chapter']} - {item['preview']}")

    print("\n✅ 检查完成")


if __name__ == "__main__":
    main()