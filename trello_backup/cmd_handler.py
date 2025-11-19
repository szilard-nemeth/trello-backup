import atexit
import logging
from typing import List

from pythoncommons.file_utils import FileUtils

from trello_backup.cli.common import TrelloContext
from trello_backup.config_parser.config import TrelloCfg
from trello_backup.constants import FilePath
from trello_backup.display.console import CliLogger
from trello_backup.display.output import OutputHandler, TrelloCardHtmlGeneratorMode
from trello_backup.http_server import HttpServer
from trello_backup.trello.api import TrelloApi
from trello_backup.trello.service import TrelloOperations

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


class MainCommandHandler:
    def __init__(self, ctx: TrelloContext):
        self.ctx = ctx

    def backup_board(self, board_name: str):
        atexit.register(HttpServer.stop_server)
        html_gen_config = TrelloCardHtmlGeneratorMode.BASIC.value
        trello_ops = TrelloOperations()
        board = trello_ops.get_board(board_name, download_comments=html_gen_config.include_comments)

        out = OutputHandler(board, html_gen_config)
        out.write_outputs()
        trello_ops.cache.save()

        # Serve attachment files for CSV output
        if self.ctx.config.get(TrelloCfg.SERVE_ATTACHMENTS):
            HttpServer.launch_http_server(dir=FilePath.OUTPUT_DIR_ATTACHMENTS)


        # TODO IDEA: HTML output file per list,
        #  only include: card name (bold), description (plain text), Checklists with check items
        #  Add WARNING text if has attachment OR add attachment links

        # TODO add file cache that stores in the following hierarchy:
        #  <maindir>/boards/<board>/cards/<card>/actions/<action_id>.json

    def print_cards(self, board: str, lists: List[str]):
        pass




