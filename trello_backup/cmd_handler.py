import atexit
import logging

from pythoncommons.file_utils import FileUtils

from trello_backup.cli.common import TrelloContext
from trello_backup.config_parser.config import TrelloCfg
from trello_backup.constants import FilePath
from trello_backup.display.console import CliLogger
from trello_backup.display.output import OutputHandler, TrelloCardHtmlGeneratorMode
from trello_backup.http_server import HttpServer
from trello_backup.trello.api import TrelloUtils
from trello_backup.trello.cache import WebpageTitleCache
from trello_backup.trello.model import TrelloBoard
from trello_backup.trello.controller import TrelloObjectParser, TrelloOperations

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


class MainCommandHandler:
    def __init__(self, ctx: TrelloContext):
        self.ctx = ctx

    def backup_board(self):
        atexit.register(HttpServer.stop_server)

        # TODO ASAP Hack! Move to TrelloApi.init()
        token = self.ctx.config.get_secret(TrelloCfg.TRELLO_TOKEN)
        api_key = self.ctx.config.get_secret(TrelloCfg.TRELLO_API_KEY)
        TrelloUtils.auth_query_params = {
            'key': api_key,
            'token': token
        }
        TrelloUtils.authorization_headers = {
            "Authorization": "OAuth oauth_consumer_key=\"{}\", oauth_token=\"{}\"".format(api_key, token)
        }

        html_gen_config = TrelloCardHtmlGeneratorMode.BASIC.value

        # TODO ASAP are these required here? Can we move it to FilePath directly?
        FileUtils.ensure_dir_created(FilePath.TRELLO_OUTPUT_DIR)
        FileUtils.ensure_dir_created(FilePath.OUTPUT_DIR_ATTACHMENTS)

        trello_ops = TrelloOperations()
        board = trello_ops.get_board("Cloudera", download_comments=html_gen_config.include_comments)

        out = OutputHandler(board, html_gen_config)
        out.write_outputs(trello_ops.cache)

        # Serve attachment files for CSV output
        if self.ctx.config.get(TrelloCfg.SERVE_ATTACHMENTS):
            HttpServer.launch_http_server(dir=FilePath.OUTPUT_DIR_ATTACHMENTS)


        # TODO IDEA: HTML output file per list,
        #  only include: card name (bold), description (plain text), Checklists with check items
        #  Add WARNING text if has attachment OR add attachment links

        # TODO add file cache that stores in the following hierarchy:
        #  <maindir>/boards/<board>/cards/<card>/actions/<action_id>.json




