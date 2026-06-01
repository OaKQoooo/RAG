"""
Step 2: 文档结构化（层级解析 → all_docs_final.json）

读取 step1 输出的坐标 JSON，按正则识别三级层级：
  L1：章（1 总则 / 第一章 / 附录A）
  L2：节（1.1 一般规定）
  L3：条款（1.0.1 具体规定文本）

输出 all_docs_final.json，作为 step3.py 向量入库的数据源。现在该模块既可命令行运行，
也可被 FastAPI/Spring 触发的入库流程调用。
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from rag_config import FINAL_JSON_PATH, STEP1_OUTPUT_DIR, ensure_runtime_dirs


INPUT_FOLDER = STEP1_OUTPUT_DIR
OUTPUT_FILE = FINAL_JSON_PATH

# L1: 识别 1 总则, 第一章, 附录A 等
L1_PATTERN = r"^(附录[A-Z]|[1-9]\d{0,1}|第[一二三四五六七八九十]+[章篇])[\s|\.]*\s*([\u4e00-\u9fa5A-Za-z0-9\s、，,（）()·\-]{2,60})$"
# L2: 识别 1.1 一般规定
L2_PATTERN = r"^([A-Z\d]+\.[1-9]\d{0,1})\s+([\u4e00-\u9fa5\s]+)$"
# L3: 识别 1.0.1 或 1.1.1
L3_PATTERN = r"^([A-Z\d]+\.\d+\.\d+)\s*(.*)$"
# TABLE: 识别 表12.3.3、表B.1 等
TABLE_TITLE_PATTERN = r"^(表\s*(?:[A-Z]\.)?\d+(?:\.\d+)*)\s*(.*)$"


def clean_source_name(filename: str) -> str:
    name = filename.replace(".json", "").replace(".pdf", "").replace("+", " ")
    name = re.sub(r"([A-Z]+)\s*T", r"\1/T", name)
    return name


def table_to_markdown(table) -> str:
    if not table:
        return ""
    md = "\n\n"
    for i, row in enumerate(table):
        clean_row = [str(c).replace("\n", "<br>").strip() if c else "-" for c in row]
        md += "| " + " | ".join(clean_row) + " |\n"
        if i == 0:
            md += "| " + " | ".join(["---"] * len(row)) + " |\n"
    return md + "\n"


def _region(page: int, document_page, page_width, page_height, bbox, kind: str, content: str = "") -> dict:
    return {
        "page": page,
        "document_page": document_page,
        "page_width": page_width,
        "page_height": page_height,
        "bbox": list(bbox),
        "kind": kind,
        "content": content,
    }


def _append_region(item: dict, region: dict) -> None:
    item.setdefault("evidence_regions", []).append(region)
    item.setdefault("bboxes", []).append(region["bbox"])


def _append_l3(cur_l1: dict, cur_l2: dict | None, item: dict) -> None:
    if cur_l2:
        cur_l2["sub_articles"].append(item)
    else:
        cur_l1["sub_articles"].append(item)


def calculate_final_bbox(item: dict) -> None:
    regions = item.get("evidence_regions") or []
    primary_page = item.get("page")
    page_regions = [region for region in regions if region.get("page") == primary_page]
    bboxes = [region["bbox"] for region in page_regions if region.get("bbox")] or item.get("bboxes", [])
    if bboxes:
        xs = [b[0] for b in bboxes] + [b[2] for b in bboxes]
        ys = [b[1] for b in bboxes] + [b[3] for b in bboxes]
        item["final_bbox"] = [min(xs), min(ys), max(xs), max(ys)]
        item["bbox_json"] = json.dumps(item["final_bbox"], ensure_ascii=False)
        item.pop("bboxes")
    for sub in item.get("sub_articles", []):
        calculate_final_bbox(sub)


def _read_step1_file(path: Path) -> tuple[dict, list[dict]]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # 兼容旧版 step1 输出：最外层就是 pages 数组。
    if isinstance(payload, list):
        return {"source_pdf": path.name}, payload
    return payload, payload.get("pages", [])


def parse_step1_json(path: Path) -> list[dict]:
    meta, pages = _read_step1_file(path)
    source_display = clean_source_name(meta.get("source_pdf") or path.name)
    document_id = meta.get("document_id")
    uploaded_by = meta.get("uploaded_by")
    source_path = meta.get("source_path")

    print(f"📦 正在处理文档: {source_display}")
    doc_structure = []
    cur_l1 = cur_l2 = cur_l3 = None
    content_started = False
    stop_parsing = False

    for page in pages:
        if stop_parsing:
            break
            
        p_num = int(page["page"])
        document_page = page.get("document_page")
        page_width = page.get("page_width")
        page_height = page.get("page_height")

        for el in page["elements"]:
            if el["type"] == "text":
                raw_line = el["text"].strip()
                clean_line = raw_line.replace(" ", "").replace("　", "")
                if not raw_line:
                    continue

                # 遇到条文说明后停止解析正文，避免条文说明重复正文条款号
                if content_started and clean_line in {"条文说明", "本规范用词说明", "引用标准名录"}:
                    print(f"  -> [STOP] 在第 {p_num} 页停止解析 (匹配词: '{clean_line}')")
                    stop_parsing = True
                    break

                if not content_started:
                    is_start_title = p_num < 20 and re.match(r"^[1一](总则|范围|概述|基本规定)", clean_line)
                    is_direct_clause = re.match(r"^1\.0\.1", clean_line)

                    if is_start_title or is_direct_clause:
                        content_started = True
                        print(f"  -> [OK] 在第 {p_num} 页开启解析 (匹配词: '{clean_line[:10]}')")
                    else:
                        continue

                if any(x in raw_line for x in ["DL/T", "GB/T", "SL/T", "出版", "北京", "ICS", "CCS", "发布", "实施"]):
                    continue
                if re.match(r"^\d+$", raw_line):
                    continue

                m1 = re.match(L1_PATTERN, raw_line)
                m2 = re.match(L2_PATTERN, raw_line)
                m3 = re.match(L3_PATTERN, raw_line)
                table_title = re.match(TABLE_TITLE_PATTERN, raw_line)

                common = {
                    "source": source_display,
                    "source_path": source_path,
                    "document_id": document_id,
                    "uploaded_by": uploaded_by,
                }
                if m1:
                    cur_l1 = {"title": raw_line, "sub_articles": [], "type": "L1", **common}
                    doc_structure.append(cur_l1)
                    cur_l2 = cur_l3 = None
                elif m2:
                    cur_l2 = {"title": raw_line, "sub_articles": [], "type": "L2", **common}
                    if not cur_l1:
                        cur_l1 = {"title": "未识别章节", "sub_articles": [], "type": "L1", **common}
                        doc_structure.append(cur_l1)
                    cur_l1["sub_articles"].append(cur_l2)
                    cur_l3 = None
                elif m3:
                    num, rest = m3.groups()
                    if not cur_l1:
                        cur_l1 = {"title": "未识别章节", "sub_articles": [], "type": "L1", **common}
                        doc_structure.append(cur_l1)
                    cur_l3 = {
                        "id": num,
                        "content": rest,
                        "page": p_num,
                        "document_page": document_page,
                        "page_width": page_width,
                        "page_height": page_height,
                        "bboxes": [],
                        "evidence_regions": [],
                        "type": "L3",
                        **common,
                    }
                    _append_region(
                        cur_l3,
                        _region(p_num, document_page, page_width, page_height, el["bbox"], "text", raw_line),
                    )
                    _append_l3(cur_l1, cur_l2, cur_l3)
                elif table_title:
                    if not cur_l1:
                        cur_l1 = {"title": "未识别章节", "sub_articles": [], "type": "L1", **common}
                        doc_structure.append(cur_l1)
                    table_id = table_title.group(1).replace(" ", "")
                    cur_l3 = {
                        "id": table_id,
                        "content": raw_line,
                        "page": p_num,
                        "document_page": document_page,
                        "page_width": page_width,
                        "page_height": page_height,
                        "bboxes": [],
                        "evidence_regions": [],
                        "type": "TABLE",
                        **common,
                    }
                    _append_region(
                        cur_l3,
                        _region(p_num, document_page, page_width, page_height, el["bbox"], "text", raw_line),
                    )
                    _append_l3(cur_l1, cur_l2, cur_l3)
                elif cur_l3:
                    cur_l3["content"] += "\n" + raw_line
                    _append_region(
                        cur_l3,
                        _region(p_num, document_page, page_width, page_height, el["bbox"], "text", raw_line),
                    )

            elif el["type"] == "table" and content_started and cur_l3:
                markdown = table_to_markdown(el["data"])
                cur_l3["content"] += markdown
                _append_region(
                    cur_l3,
                    _region(p_num, document_page, page_width, page_height, el["bbox"], "table", markdown),
                )

    for l1 in doc_structure:
        calculate_final_bbox(l1)
    return doc_structure


def build_structured_dataset(input_folder=INPUT_FOLDER, output_file=OUTPUT_FILE) -> list[dict]:
    ensure_runtime_dirs()
    input_folder = Path(input_folder)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    all_structured_data = []
    for file_json in os.listdir(input_folder):
        if file_json.endswith(".json"):
            all_structured_data.extend(parse_step1_json(input_folder / file_json))

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_structured_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 逻辑提取完成！汇总数据已保存至 {output_file}")
    print(f"📊 最终统计：共处理 {len(all_structured_data)} 个章节。")
    return all_structured_data


def parse_args():
    parser = argparse.ArgumentParser(description="Step2 文档层级结构化")
    parser.add_argument("--input-dir", default=str(INPUT_FOLDER), help="step1 JSON 输出目录")
    parser.add_argument("--output", default=str(OUTPUT_FILE), help="结构化 JSON 输出文件")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_structured_dataset(args.input_dir, args.output)
