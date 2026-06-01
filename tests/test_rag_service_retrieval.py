import unittest

from langchain_core.documents import Document

from rag_service import DebugSearchRequest, RagEngine


class FailingVectorStore:
    def similarity_search_with_score(self, *_args, **_kwargs):
        raise RuntimeError("embedding unavailable")


class PassthroughReranker:
    def compress_documents(self, documents, _question):
        return list(documents)


class RagServiceRetrievalTest(unittest.TestCase):
    def test_falls_back_to_lexical_candidates_when_vector_search_fails(self):
        engine = RagEngine.__new__(RagEngine)
        engine.vector_store = FailingVectorStore()
        engine.reranker = PassthroughReranker()
        engine.lexical_documents = [
            Document(
                page_content="施工导流应符合设计要求。",
                metadata={
                    "document_id": "1",
                    "source_file": "DL/T 5128-2021 示例规范",
                    "chapter": "4.2 导流",
                    "clause_id": "4.2.1",
                    "clause_key": "DL/T 5128-2021::4.2.1",
                    "chunk_index": 0,
                },
            )
        ]

        docs = engine._retrieve_documents(DebugSearchRequest(question="导流有什么要求？"))

        self.assertEqual(1, len(docs))
        self.assertEqual("4.2.1", docs[0].metadata["clause_id"])
        self.assertGreater(docs[0].metadata["_lexical_score"], 0)


if __name__ == "__main__":
    unittest.main()
