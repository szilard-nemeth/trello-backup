import unittest

from trello_backup.trello.html import HtmlParser


class TestHtmlParserJsFallback(unittest.TestCase):
    def test_title_needs_js_fallback_placeholder_youtube(self):
        self.assertTrue(HtmlParser._title_needs_js_fallback(" - YouTube"))
        self.assertTrue(HtmlParser._title_needs_js_fallback("- YouTube"))

    def test_title_needs_js_fallback_real_title(self):
        self.assertFalse(HtmlParser._title_needs_js_fallback("Autumn Process - YouTube"))
