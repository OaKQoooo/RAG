import unittest

from page_number import detect_document_page


class FakePage:
    width = 600
    height = 800

    def __init__(self, footer):
        self.footer = footer

    def crop(self, _bbox):
        return self

    def extract_text(self):
        return self.footer


class DocumentPageDetectionTest(unittest.TestCase):
    def test_detects_common_footer_formats(self):
        self.assertEqual("12", detect_document_page(FakePage("正文\n第 12 页"), 20))
        self.assertEqual("8", detect_document_page(FakePage("正文\n- 8 -"), 20))
        self.assertEqual("3", detect_document_page(FakePage("正文\n3 / 40"), 20))

    def test_manual_offset_takes_priority(self):
        self.assertEqual("5", detect_document_page(FakePage("第 99 页"), 13, 8))

    def test_manual_offset_ignores_non_positive_front_matter(self):
        self.assertIsNone(detect_document_page(FakePage(""), 4, 8))


if __name__ == "__main__":
    unittest.main()
