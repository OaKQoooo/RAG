import unittest

from evaluate_retrieval import evaluate_case, normalize_clause_id


class EvaluateRetrievalTest(unittest.TestCase):
    def test_normalizes_split_clause_suffix(self):
        self.assertEqual("A.6.2", normalize_clause_id("A.6.2_p11"))

    def test_reports_first_expected_clause_rank(self):
        report = evaluate_case(
            {"question": "question", "expected_clause_ids": ["4.2.1"]},
            [
                {"metadata": {"clause_id": "3.1.1"}},
                {"metadata": {"clause_id": "4.2.1_p0"}},
            ],
        )

        self.assertTrue(report["hit"])
        self.assertEqual(2, report["first_hit_rank"])
        self.assertEqual(0.5, report["reciprocal_rank"])


if __name__ == "__main__":
    unittest.main()
