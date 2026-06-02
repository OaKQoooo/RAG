import unittest

from check_ingest_quality import build_quality_report_for_data


class IngestQualityReportTest(unittest.TestCase):
    def test_counts_duplicate_clause_ids_within_one_document(self):
        data = [
            {
                "type": "L1",
                "title": "1 General",
                "document_id": "doc-a",
                "sub_articles": [
                    self.clause("doc-a", "1.0.1", "first"),
                    self.clause("doc-a", "1.0.1", "second"),
                ],
            }
        ]

        report = build_quality_report_for_data(data)

        self.assertEqual(2, report["total_clauses"])
        self.assertEqual(1, report["duplicate_within_document_count"])
        self.assertEqual(0, report["duplicate_across_documents_count"])

    def test_distinguishes_cross_document_clause_ids(self):
        data = [
            self.chapter("doc-a", self.clause("doc-a", "1.0.1", "first")),
            self.chapter("doc-b", self.clause("doc-b", "1.0.1", "second")),
        ]

        report = build_quality_report_for_data(data)

        self.assertEqual(0, report["duplicate_within_document_count"])
        self.assertEqual(1, report["duplicate_across_documents_count"])

    def test_allows_same_table_id_for_distinct_parts(self):
        data = [
            self.chapter(
                "doc-a",
                self.table("doc-a", "表4.0.3", 14, "[1, 2, 3, 4]"),
                self.table("doc-a", "表4.0.3", 15, "[1, 2, 3, 4]"),
                self.table("doc-a", "表4.0.3", 15, "[5, 6, 7, 8]"),
            )
        ]

        report = build_quality_report_for_data(data)

        self.assertEqual(3, report["total_clauses"])
        self.assertEqual(0, report["duplicate_within_document_count"])

    def test_detects_exact_duplicate_table_parts(self):
        data = [
            self.chapter(
                "doc-a",
                self.table("doc-a", "表4.0.3", 14, "[1, 2, 3, 4]"),
                self.table("doc-a", "表4.0.3", 14, "[1, 2, 3, 4]"),
            )
        ]

        report = build_quality_report_for_data(data)

        self.assertEqual(1, report["duplicate_within_document_count"])

    @staticmethod
    def chapter(document_id, *clauses):
        return {
            "type": "L1",
            "title": "1 General",
            "document_id": document_id,
            "sub_articles": list(clauses),
        }

    @staticmethod
    def clause(document_id, clause_id, content):
        return {
            "type": "L3",
            "id": clause_id,
            "content": content,
            "page": 1,
            "bbox_json": "[1, 2, 3, 4]",
            "document_id": document_id,
        }

    @staticmethod
    def table(document_id, clause_id, page, bbox_json):
        return {
            "type": "TABLE",
            "id": clause_id,
            "content": f"{clause_id} markdown table",
            "page": page,
            "bbox_json": bbox_json,
            "document_id": document_id,
        }


if __name__ == "__main__":
    unittest.main()
