import json
import tempfile
import unittest
from pathlib import Path

from check_ingest_quality import build_quality_report_for_data
from step3 import CHUNK_SIZE, flatten_items, load_documents, select_evidence_region, split_content


class Step3ChunkingTest(unittest.TestCase):
    def test_hard_splits_punctuation_free_oversized_text(self):
        chunks = split_content("水" * (CHUNK_SIZE * 2 + 50))

        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= CHUNK_SIZE for chunk in chunks))

    def test_keeps_short_paragraph_intact(self):
        self.assertEqual(["短条款内容。"], split_content("短条款内容。"))

    def test_keeps_short_table_title_and_markdown_in_one_chunk(self):
        content = "表4.0.3 运行阶段等级划分\n\n| 等级 | 说明 |\n| --- | --- |\n| 1 | 低风险 |"

        self.assertEqual([content], split_content(content, preserve_table=True))

    def test_repeated_table_ids_receive_distinct_internal_clause_keys(self):
        payload = [
            {
                "type": "L1",
                "title": "4 基本规定",
                "source": "SLT829-2024示例规范",
                "sub_articles": [
                    {"type": "TABLE", "id": "表4.0.3", "content": "表4.0.3 1 可能性等级"},
                    {"type": "TABLE", "id": "表4.0.3", "content": "表4.0.3 2 后果等级"},
                    {"type": "TABLE", "id": "表4.0.3", "content": "表4.0.3 3 风险等级"},
                ],
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "structured.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            docs = load_documents(path)

        self.assertEqual(
            [
                "SL/T 829-2024示例规范::表4.0.3#part1",
                "SL/T 829-2024示例规范::表4.0.3#part2",
                "SL/T 829-2024示例规范::表4.0.3#part3",
            ],
            [doc.metadata["clause_key"] for doc in docs],
        )
        self.assertEqual([1, 2, 3], [doc.metadata["table_part"] for doc in docs])

    def test_long_clause_chunks_do_not_create_structured_duplicates(self):
        payload = [
            {
                "type": "L1",
                "title": "1 General",
                "document_id": "doc-a",
                "source": "SLT829-2024示例规范",
                "sub_articles": [
                    {
                        "type": "L3",
                        "id": "1.0.1",
                        "content": "长" * (CHUNK_SIZE * 2 + 50),
                        "page": 1,
                        "bbox_json": "[1, 2, 3, 4]",
                        "document_id": "doc-a",
                    }
                ],
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "structured.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            docs = load_documents(path)

        report = build_quality_report_for_data(payload)
        self.assertGreater(len(docs), 1)
        self.assertEqual(["1.0.1_p0", "1.0.1_p1", "1.0.1_p2"], [doc.metadata["clause_id"] for doc in docs])
        self.assertEqual(0, report["duplicate_within_document_count"])

    def test_preserves_full_chapter_path_for_clause_indexing(self):
        items = []
        flatten_items(
            {
                "type": "L1",
                "title": "4 施工导流",
                "sub_articles": [
                    {
                        "type": "L2",
                        "title": "4.2 导流",
                        "sub_articles": [{"type": "L3", "id": "4.2.1", "content": "正文"}],
                    }
                ],
            },
            items,
        )

        self.assertEqual("4 施工导流 > 4.2 导流", items[0]["_chapter_path"])

    def test_prefers_table_region_for_markdown_table_chunk(self):
        item = {
            "page": 1,
            "evidence_regions": [
                {"kind": "text", "page": 1, "bbox": [1, 2, 3, 4], "content": "表B.1"},
                {"kind": "table", "page": 2, "bbox": [10, 20, 300, 400], "content": "| 序号 | 项目 |"},
            ],
        }

        region = select_evidence_region(item, "| 序号 | 项目 |\n| --- | --- |")

        self.assertEqual("table", region["kind"])
        self.assertEqual(2, region["page"])
        self.assertEqual([10, 20, 300, 400], region["bbox"])


if __name__ == "__main__":
    unittest.main()
