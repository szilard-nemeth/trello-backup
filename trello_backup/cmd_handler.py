import atexit

from pythoncommons.file_utils import FileUtils

from trello_backup.cli.common import TrelloContext
from trello_backup.config_parser.config import TrelloCfg
from trello_backup.constants import FilePath
from trello_backup.display.output import OutputHandler
from trello_backup.http_server import HttpServer
from trello_backup.trello.api import TrelloUtils
from trello_backup.trello.cache import WebpageTitleCache
from trello_backup.trello.model import TrelloBoard
from trello_backup.trello_backup import *

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


class MainCommandHandler:
    def __init__(self, ctx: TrelloContext):
        self.ctx = ctx

    def backup_board(self):
        atexit.register(HttpServer.stop_server)

        # TODO Hack!
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

        FileUtils.ensure_dir_created(FilePath.TRELLO_OUTPUT_DIR)
        FileUtils.ensure_dir_created(FilePath.OUTPUT_DIR_ATTACHMENTS)

        board_name = 'Cloudera'
        board_id = TrelloApi.get_board_id(board_name)
        board_details_json = TrelloApi.get_board_details(board_id)

        # 1. parse lists
        trello_lists_all = parse_trello_lists(board_details_json)
        trello_lists_by_id = {l.id: l for l in trello_lists_all}

        # 2. Parse checklists
        trello_checklists = parse_trello_checklists(board_details_json)
        trello_checklists_by_id = {c.id: c for c in trello_checklists}

        trello_cards_all = parse_trello_cards(board_details_json, trello_lists_by_id, trello_checklists_by_id, html_gen_config)
        trello_cards_open = list(filter(lambda c: not c.closed, trello_cards_all))

        # Filter open trello lists
        trello_lists_open = list(filter(lambda tl: not tl.closed, trello_lists_all))
        print(trello_lists_open)

        WebpageTitleCache.load()
        board = TrelloBoard(board_id, board_name, trello_lists_open)
        board.get_checklist_url_titles()

        # Download attachments
        TrelloApi.download_attachments(board)

        out = OutputHandler(board, html_gen_config)
        out.write_outputs()

        # Serve attachment files for CSV output
        if self.ctx.config.get(TrelloCfg.SERVE_ATTACHMENTS):
            HttpServer.launch_http_server(dir=FilePath.OUTPUT_DIR_ATTACHMENTS)


        # TODO IDEA: HTML output file per list,
        #  only include: card name (bold), description (plain text), Checklists with check items
        #  Add WARNING text if has attachment OR add attachment links

        # TODO add file cache that stores in the following hierarchy:
        #  <maindir>/boards/<board>/cards/<card>/actions/<action_id>.json




