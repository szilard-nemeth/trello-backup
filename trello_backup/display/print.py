import logging

from rich.markdown import Markdown

from trello_backup.display.console import CliLogger, TextStyle

LOG = logging.getLogger(__name__)
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
