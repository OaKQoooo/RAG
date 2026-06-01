import unittest

from step3 import CHUNK_SIZE, flatten_items, select_evidence_region, split_content


class Step3ChunkingTest(unittest.TestCase):
    def test_hard_splits_punctuation_free_oversized_text(self):
        chunks = split_content("水" * (CHUNK_SIZE * 2 + 50))

        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= CHUNK_SIZE for chunk in chunks))

    def test_keeps_short_paragraph_intact(self):
        self.assertEqual(["短条款内容。"], split_content("短条款内容。"))

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
