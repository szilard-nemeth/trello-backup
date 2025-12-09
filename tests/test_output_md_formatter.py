import unittest
from trello_backup.display.output import MarkdownFormatter


class TestMarkdownFormatter(unittest.TestCase):

    def setUp(self):
        self.fmt = MarkdownFormatter()

    # ------------------------
    # Tests for to_plain_text (covers unmark_element)
    # ------------------------

    def test_unmark_simple_text(self):
        self.assertEqual(
            self.fmt.to_plain_text("Hello world"),
            "Hello world"
        )

    def test_unmark_nested_tags(self):
        self.assertEqual(
            self.fmt.to_plain_text("Hello **bold** text"),
            "Hello bold text"
        )

    def test_unmark_links(self):
        self.assertEqual(
            self.fmt.to_plain_text("Click [here](https://example.com) now"),
            "Click here now"
        )

    def test_unmark_list(self):
        text = self.fmt.to_plain_text("- item1\n- item2")
        self.assertIn("item1", text)
        self.assertIn("item2", text)

    def test_unmark_inline_code(self):
        self.assertEqual(
            self.fmt.to_plain_text("Run `code` now"),
            "Run code now"
        )

    def test_to_plain_text_basic(self):
        self.assertEqual(
            self.fmt.to_plain_text("Hello **world**"),
            "Hello world"
        )

    def test_to_plain_text_strips_zwnj(self):
        zwnj = "\u200c"
        result = self.fmt.to_plain_text(f"Hel{zwnj}lo")
        self.assertEqual(result, "Hello")
        self.assertNotIn(zwnj, result)

    def test_to_plain_text_with_link(self):
        self.assertEqual(
            self.fmt.to_plain_text("Visit [Google](https://google.com) now."),
            "Visit Google now."
        )

    def test_to_plain_text_special_char(self):
        self.assertEqual(
            self.fmt.to_plain_text("i'm good"),
            "i'm good"
        )
        self.assertEqual(
            self.fmt.to_plain_text("i'm good"),
            "i'm good"
        )
        self.assertEqual(self.fmt.to_plain_text("I’m good"),
                         "I’m good")

    def test_to_plain_text_complex(self):
        text = """
# Title

Paragraph with **bold**, *italic*, and [link](http://example.com).

- Item A
- Item B
"""
        out = self.fmt.to_plain_text(text)
        self.assertIn("Title", out)
        self.assertIn("Paragraph with bold, italic, and link.", out)
        self.assertIn("Item A", out)
        self.assertIn("Item B", out)


if __name__ == "__main__":
    unittest.main()
