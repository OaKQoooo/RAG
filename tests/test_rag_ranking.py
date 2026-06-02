import unittest

from rag_ranking import (
    classify_standard_level,
    extract_standard_code,
    lexical_relevance_score,
    merge_candidates,
    normalize_standard_name,
    rank_documents,
)


class FakeDocument:
    def __init__(self, content, **metadata):
        self.page_content = content
        self.metadata = metadata


class StandardClassificationTest(unittest.TestCase):
    def test_normalizes_uploaded_industry_standard_name(self):
        source = "admin_1_20260531192419_DLT5128-2021混凝土面板堆石坝施工规范.pdf"

        self.assertEqual("DL/T 5128-2021混凝土面板堆石坝施工规范", normalize_standard_name(source))
        self.assertEqual("DL/T5128-2021", extract_standard_code(source))
        self.assertEqual("industry", classify_standard_level(source))

    def test_classifies_common_standard_levels(self):
        self.assertEqual("national_mandatory", classify_standard_level("GB 50010-2010 混凝土结构设计规范"))
        self.assertEqual("national_recommended", classify_standard_level("GB/T 1234-2020 示例规范"))
        self.assertEqual("local", classify_standard_level("DB11/T 123-2024 示例规范"))
        self.assertEqual("group", classify_standard_level("T/CECS 123-2024 示例规范"))
        self.assertEqual("enterprise", classify_standard_level("Q/ACME 123-2024 公司标准"))


class RankingTest(unittest.TestCase):
    def test_uses_standard_hierarchy_as_tie_breaker(self):
        national = self.document("GB 50010-2010 示例规范", "national")
        industry = self.document("DL/T 5128-2021 示例规范", "industry")

        ranked = rank_documents([industry, national], "施工要求是什么")

        self.assertIs(national, ranked[0])

    def test_explicit_industry_intent_can_outrank_default_hierarchy(self):
        national = self.document("GB 50010-2010 示例规范", "national")
        industry = self.document("DL/T 5128-2021 示例规范", "industry")

        ranked = rank_documents([national, industry], "行业标准中施工要求是什么")

        self.assertIs(industry, ranked[0])

    def test_exact_standard_code_receives_a_boost(self):
        first = self.document("DL/T 5128-2021 示例规范", "first")
        second = self.document("DL/T 5112-2021 示例规范", "second")

        ranked = rank_documents([second, first], "DL/T 5128-2021 的施工要求是什么")

        self.assertIs(first, ranked[0])
        self.assertGreater(first.metadata["_standard_code_bonus"], 0)

    def test_limits_repeated_chunks_from_one_clause(self):
        docs = [
            self.document("DL/T 5128-2021 示例规范", f"chunk-{index}", clause_key="same", chunk_index=index)
            for index in range(3)
        ]
        other = self.document("DL/T 5128-2021 示例规范", "other", clause_key="other", chunk_index=0)

        ranked = rank_documents([*docs, other], "施工要求是什么", max_chunks_per_clause=2)

        self.assertIn(other, ranked[:3])

    def test_deduplicates_repeated_chunks_from_one_clause_by_default(self):
        docs = [
            self.document("DL/T 5128-2021 example", f"chunk-{index}", clause_key="same", chunk_index=index)
            for index in range(3)
        ]

        ranked = rank_documents(docs, "construction requirements")

        self.assertEqual(1, len(ranked))

    def test_deduplicates_same_clause_from_repeated_uploads(self):
        first = self.document("DL/T 5128-2021 example", "first", clause_id="6.5.5_p0", clause_key="DL/T 5128-2021 example::6.5.5")
        second = self.document("DL/T 5128-2021 example", "second", clause_id="6.5.5_p1", clause_key="DL/T 5128-2021 example::6.5.5")
        second.metadata["document_id"] = "2"

        ranked = rank_documents([first, second], "construction requirements")

        self.assertEqual(1, len(ranked))

    def test_merges_same_clause_from_repeated_uploads_before_reranking(self):
        first = self.document("DL/T 5128-2021 example", "first", clause_key="same")
        second = self.document("DL/T 5128-2021 example", "second", clause_key="same")
        second.metadata["document_id"] = "2"

        merged = merge_candidates([first], [second])

        self.assertEqual(1, len(merged))

    def test_lexical_score_rewards_specific_chapter_match(self):
        chapter_match = self.document("DL/T 5128-2021 示例规范", "施工准备", chapter="4.2 导流")
        generic_content = self.document("DL/T 5128-2021 示例规范", "施工准备中的基本规定", chapter="附录")

        self.assertGreater(
            lexical_relevance_score(chapter_match, "施工导流有哪些基本规定？"),
            lexical_relevance_score(generic_content, "施工导流有哪些基本规定？"),
        )

    @staticmethod
    def document(source, content, **metadata):
        return FakeDocument(
            content,
            source_file=source,
            document_id="1",
            clause_id=metadata.pop("clause_id", "1.0.1"),
            clause_key=metadata.pop("clause_key", content),
            chunk_index=metadata.pop("chunk_index", 0),
            _vector_score=0.5,
            _rerank_score=0.5,
            **metadata,
        )


if __name__ == "__main__":
    unittest.main()
