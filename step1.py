"""
Step 1: PDF 解析（坐标级元素提取）

使用 pdfplumber 对每份规范 PDF 进行逐页解析：
  - 识别并提取页内表格（保留 bbox 坐标）
  - 提取表格区域外的文本行（同样保留 bbox）
  - 将元素按垂直位置排序，输出为 JSON 文件供 step2.py 使用

注意：此模块保留完整的自定义坐标解析逻辑，不使用 LangChain 的通用 PDF Loader，
      以确保表格识别和行级 bbox 的精度。
"""

import argparse
import json
import os
from pathlib import Path

import pdfplumber

from rag_config import PDF_DIR, STEP1_OUTPUT_DIR, ensure_runtime_dirs

# --- 配置区 ---
PDF_FOLDER = PDF_DIR
OUTPUT_FOLDER = STEP1_OUTPUT_DIR
ensure_runtime_dirs()

def is_obj_in_bbox(obj, bboxes):
    obj_mid_h = (obj["x0"] + obj["x1"]) / 2
    obj_mid_v = (obj["top"] + obj["bottom"]) / 2
    for bbox in bboxes:
        x0, top, x1, bottom = bbox
        if (obj_mid_h >= x0 and obj_mid_h <= x1) and (obj_mid_v >= top and obj_mid_v <= bottom):
            return True
    return False

def process_single_pdf(pdf_path, output_folder=OUTPUT_FOLDER, document_id=None, uploaded_by=None):
    """Parse one PDF and write page elements with bbox metadata to JSON."""
    pdf_path = Path(pdf_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    file_name = pdf_path.name
    results = []
    print(f"正在解析: {file_name}...")

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            tables_found = page.find_tables()
            table_bboxes = [t.bbox for t in tables_found]
            elements = []

            for t in tables_found:
                elements.append({
                    "type": "table",
                    "top": t.bbox[1],
                    "data": t.extract(),
                    "bbox": list(t.bbox)
                })

            clean_page = page.filter(lambda obj: not is_obj_in_bbox(obj, table_bboxes))
            text_lines = clean_page.extract_text_lines()
            for line in text_lines:
                elements.append({
                    "type": "text",
                    "top": line["top"],
                    "text": line["text"].strip(),
                    "bbox": [line["x0"], line["top"], line["x1"], line["bottom"]]
                })

            results.append({
                "page": page_num,
                "page_width": page.width,
                "page_height": page.height,
                "elements": sorted(elements, key=lambda x: x["top"])
            })

    out_name = output_folder / file_name.replace(".pdf", ".json")
    with open(out_name, "w", encoding="utf-8") as f:
        json.dump(
            {
                "document_id": document_id,
                "uploaded_by": uploaded_by,
                "source_pdf": file_name,
                "pages": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return str(out_name)


def process_folder(pdf_folder=PDF_FOLDER, output_folder=OUTPUT_FOLDER):
    outputs = []
    pdf_folder = Path(pdf_folder)
    for file in os.listdir(pdf_folder):
        if file.lower().endswith(".pdf"):
            outputs.append(process_single_pdf(pdf_folder / file, output_folder))
    return outputs


def parse_args():
    parser = argparse.ArgumentParser(description="Step1 PDF 坐标级解析")
    parser.add_argument("--pdf", help="只解析单个 PDF 文件")
    parser.add_argument("--pdf-dir", default=str(PDF_FOLDER), help="批量解析 PDF 目录")
    parser.add_argument("--output-dir", default=str(OUTPUT_FOLDER), help="Step1 JSON 输出目录")
    parser.add_argument("--document-id", help="后端 kb_document.id，可选")
    parser.add_argument("--uploaded-by", help="上传用户 ID，可选")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    if args.pdf:
        process_single_pdf(args.pdf, args.output_dir, args.document_id, args.uploaded_by)
    else:
        process_folder(args.pdf_dir, args.output_dir)
    print(f"✅ PDF 坐标解析完成，存放于 {args.output_dir}")
