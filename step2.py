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
L1_PATTERN = r"^(附录[A-Z]|[1-9]\d{0,1}|第[一二三四五六七八九十]+[章篇])[\s|\.]*\s*([\u4e00-\u9fa5\s]{2,30})$"
# L2: 识别 1.1 一般规定
L2_PATTERN = r"^([A-Z\d]+\.[1-9]\d{0,1})\s+([\u4e00-\u9fa5\s]+)$"
# L3: 识别 1.0.1 或 1.1.1
L3_PATTERN = r"^([A-Z\d]+\.\d+\.\d+)\s*(.*)$"


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


def calculate_final_bbox(item: dict) -> None:
    if "bboxes" in item and item["bboxes"]:
        xs = [b[0] for b in item["bboxes"]] + [b[2] for b in item["bboxes"]]
        ys = [b[1] for b in item["bboxes"]] + [b[3] for b in item["bboxes"]]
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

    print(f"📦 正在处理文档: {source_display}")
    doc_structure = []
    cur_l1 = cur_l2 = cur_l3 = None
    content_started = False

    for page in pages:
        p_num = int(page["page"])
        page_width = page.get("page_width")
        page_height = page.get("page_height")

        for el in page["elements"]:
            if el["type"] == "text":
                raw_line = el["text"].strip()
                clean_line = raw_line.replace(" ", "").replace("　", "")
                if not raw_line:
                    continue

                if not content_started:
                    is_foreword = p_num < 15 and "前言" in clean_line and len(clean_line) < 10
                    is_start_title = p_num < 15 and re.match(r"^[1一](总则|范围|概述|基本规定)", clean_line)
                    is_direct_clause = re.match(r"^1\.0\.1", clean_line)

                    if is_foreword or is_start_title or is_direct_clause:
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

                common = {"source": source_display, "document_id": document_id, "uploaded_by": uploaded_by}
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
                        "page_width": page_width,
                        "page_height": page_height,
                        "bboxes": [el["bbox"]],
                        "type": "L3",
                        **common,
                    }
                    if cur_l2:
                        cur_l2["sub_articles"].append(cur_l3)
                    else:
                        cur_l1["sub_articles"].append(cur_l3)
                elif cur_l3:
                    cur_l3["content"] += "\n" + raw_line
                    cur_l3["bboxes"].append(el["bbox"])

            elif el["type"] == "table" and content_started and cur_l3:
                cur_l3["content"] += table_to_markdown(el["data"])
                cur_l3["bboxes"].append(el["bbox"])

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
