import enum
import logging
import os.path
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.theme import Theme

import logging
LOG = logging.getLogger(__name__)

class TextStyle(enum.Enum):
    INFO = ("info", "dim cyan", logging.INFO)
    SUCCESS = ("success", "dim green", logging.INFO)
    WARNING = ("warning", "yellow", logging.WARNING)
    DANGER = ("danger", "bold red", logging.ERROR)

    def __init__(self, name: str, style: str, log_level: int):
        self.style_name = name
        self.style = style
        self.log_level = log_level


CUSTOM_THEME = Theme({t.style_name: t.style for t in TextStyle})

class ConsoleUtils:
    @classmethod
    def create_console(cls, record=False, log_to_console=True, wide=False):
        width = 80
        if wide:
            width = CliLogger.WIDE_PRINT_WIDTH

        file = open(os.devnull, "wt")
        if log_to_console:
            file = sys.stdout


        console = Console(
            record=record,
            file=file,
            color_system="truecolor", # Ensures maximum color fidelity in the HTML
            width=width
        )
        return console


class CliLogger(logging.Logger):
    _themed_console = Console(theme=CUSTOM_THEME)
    _console: Console = None
    _wide_console: Console = None
    WIDE_PRINT_WIDTH = 300

    def __init__(self, logger):
        super().__init__(logger.name)
        self._logger: logging.Logger = logger
        if not CliLogger._console:
            CliLogger._console = Console()
            CliLogger._wide_console = Console(width=CliLogger.WIDE_PRINT_WIDTH)
        self._formatter = logging.Formatter()

    def _set_file_handler(self):
        filtered_handlers = list(
            filter(lambda h: isinstance(h, logging.FileHandler), self._logger.handlers))
        if len(filtered_handlers) == 0:
            raise ValueError("Expected at least one instance of FileHandler!")
        self._file_handler: logging.FileHandler = filtered_handlers[0]

    def __getattribute__(self, item):
        if item == "handlers":
            return self._logger.handlers
        return object.__getattribute__(self, item)

    def handle(self, record):
        super(CliLogger, self).handle(record)

        if record.levelno == logging.INFO:
            formatted = self._formatter.format(record)
            # The call to 'super(CliLogger, self).handle(record)' already logged the record via the Logger instance.
            # As PrettyPrint.print_info_text will end up calling CliLogger.print_themed, we need to prevent logging the record again.
            PrettyPrint.print_info_text(formatted, suppress_logger=True)

    def print(self, obj, wide_print=False):
        width = CliLogger.WIDE_PRINT_WIDTH if wide_print else None
        if width and self._console.width < width:
            self._wide_console.print(obj, width=width)
        else:
            self._console.print(obj, width=width)

    def print_themed(self, text, text_style: TextStyle, suppress_logger=False):
        """
        This method prints the text to the console with the appropriate style and also logs it via the logger.
        :param text:
        :param text_style:
        :return:
        """
        self._themed_console.print(text, style=text_style.style_name)
        if not suppress_logger:
            self._logger.log(text_style.log_level, text)

    def print_exception(self, show_locals: bool = False):
        self._console.print_exception(show_locals=show_locals)

    def record_console(self):
        self._console.record = True
        self._wide_console.record = True
        self._themed_console.record = True

    def export_to_html(self, file_path):
        fp, ext = os.path.splitext(file_path)
        themed_file_path = f"{fp}_themed{ext}"
        wide_file_path = f"{fp}_wide{ext}"

        if not self._console.record:
            raise Exception("Cannot export to HTML, normal Console is not in recording mode!")
        if not self._themed_console.record:
            raise Exception("Cannot export to HTML, themed Console is not in recording mode!")
        if not self._wide_console.record:
            raise Exception("Cannot export to HTML, wide Console is not in recording mode!")

        self._console.save_html(file_path)
        self._themed_console.save_html(themed_file_path)
        self._wide_console.save_html(wide_file_path)

        return [file_path, themed_file_path, wide_file_path]


class Object(object):
    def __contains__(self, key):
        return key in self.__dict__


CLI_LOG = CliLogger(LOG)
class PrettyPrint:
    @staticmethod
    def print(head_line, obj):
        from rich.pretty import pprint
        from rich import print

        print(head_line)
        pprint(obj)

    @staticmethod
    def print(obj):
        from rich.pretty import pprint
        pprint(obj)

    # TODO Migrate these to CLI_LOG.print_xxx_text instance calls for each individual caller
    @staticmethod
    def print_info_text(text, suppress_logger=False):
        CLI_LOG.print_themed(text, TextStyle.INFO, suppress_logger=suppress_logger)

    @staticmethod
    def print_success_text(text, suppress_logger=False):
        CLI_LOG.print_themed(text, TextStyle.SUCCESS, suppress_logger=suppress_logger)

    @staticmethod
    def print_error_text(text, suppress_logger=False):
        CLI_LOG.print_themed(text, TextStyle.DANGER, suppress_logger=suppress_logger)

    @staticmethod
    def print_warning_text(text, suppress_logger=False):
        CLI_LOG.print_themed(text, TextStyle.WARNING, suppress_logger=suppress_logger)

    @classmethod
    def print_code_block(cls, text):
        # lines = text.split("\n")
        #markup = "<br/>".join(lines)
        md = f"```\n{text}\n```"
        markdown = Markdown(md)
        CLI_LOG.print(markdown)
