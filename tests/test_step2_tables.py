import json
import tempfile
import unittest
from pathlib import Path

from step2 import parse_step1_json


class Step2TableParsingTest(unittest.TestCase):
    def test_creates_independent_table_node_and_keeps_table_region(self):
        payload = {
            "source_pdf": "DLT5128-2021示例规范.pdf",
            "pages": [
                {
                    "page": 1,
                    "document_page": "1",
                    "page_width": 600,
                    "page_height": 800,
                    "elements": [
                        self.text("1 总则", [20, 20, 100, 40]),
                        self.text("1.0.1 正文条款。", [20, 50, 200, 70]),
                        self.text("附录B 检查项目、质量标准及检验方法", [20, 100, 300, 120]),
                        self.text("表B.1 检查项目", [20, 140, 180, 160]),
                        {
                            "type": "table",
                            "top": 180,
                            "bbox": [20, 180, 500, 300],
                            "data": [["序号", "项目"], ["1", "坝基开挖"]],
                        },
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = parse_step1_json(path)

        self.assertEqual(2, len(result))
        self.assertEqual("附录B 检查项目、质量标准及检验方法", result[1]["title"])
        table = result[1]["sub_articles"][0]
        self.assertEqual("表B.1", table["id"])
        self.assertEqual("TABLE", table["type"])
        self.assertIn("| 序号 | 项目 |", table["content"])
        self.assertEqual("table", table["evidence_regions"][-1]["kind"])
        self.assertEqual([20, 180, 500, 300], table["evidence_regions"][-1]["bbox"])

    @staticmethod
    def text(value, bbox):
        return {"type": "text", "top": bbox[1], "text": value, "bbox": bbox}


if __name__ == "__main__":
    unittest.main()
