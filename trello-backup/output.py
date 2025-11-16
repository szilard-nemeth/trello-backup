from markdown import Markdown
from io import StringIO


class MarkdownFormatter:
    def __init__(self):
        # patching Markdown
        Markdown.output_formats["plain"] = MarkdownFormatter.unmark_element
        self.__md = Markdown(output_format="plain")
        self.__md.stripTopLevelTags = False

    @staticmethod
    def unmark_element(element, stream=None):
        """
            https://stackoverflow.com/a/54923798/1106893
        """
        if stream is None:
            stream = StringIO()
        if element.text:
            stream.write(element.text)
        for sub in element:
            MarkdownFormatter.unmark_element(sub, stream)
        if element.tail:
            stream.write(element.tail)
        return stream.getvalue()

    def to_plain_text(self, text):
        converted = self.__md.convert(text)

        # Remove potential ZWNJ (0x200c) characters: https://unicodemap.org/details/0x200C/index.html
        converted2 = (converted.encode('ascii', 'ignore')).decode("utf-8")
        return converted2
