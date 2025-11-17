import atexit

from trello_backup.cli.common import TrelloContext
from trello_backup.http_server import HttpServer
from trello_backup.trello_backup import *

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)

# TODO snemeth remove this global, search for usages
webpage_title_cache = None
# TODO snemeth remove this global, search for usages
config = None

class MainCommandHandler:
    def __init__(self, ctx: TrelloContext):
        self.ctx = ctx

    def backup_board(self):
        global config
        config = self.ctx.config
        atexit.register(HttpServer.stop_server)

        validate_config()
        html_gen_config = TRELLO_CARD_GENERATOR_BASIC_CONFIG

        FileUtils.ensure_dir_created(FilePath.TRELLO_OUTPUT_DIR)
        FileUtils.ensure_dir_created(FilePath.OUTPUT_DIR_ATTACHMENTS)

        board_name = 'Cloudera'
        board_id = get_board_id(board_name)

        board_details_json = get_board_details(board_id)

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

        global webpage_title_cache
        webpage_title_cache = load_webpage_title_cache()
        board = TrelloBoard(board_id, board_name, trello_lists_open)
        board.get_checklist_url_titles()

        # Download attachments
        download_attachments(board)

        out = OutputHandler(board, html_gen_config)
        out.write_outputs()

        # Serve attachment files for CSV output
        if config.get(TrelloCfg.SERVE_ATTACHMENTS):
            HttpServer.launch_http_server(dir=FilePath.OUTPUT_DIR_ATTACHMENTS)


        # TODO IDEA: HTML output file per list,
        #  only include: card name (bold), description (plain text), Checklists with check items
        #  Add WARNING text if has attachment OR add attachment links

        # TODO add file cache that stores in the following hierarchy:
        #  <maindir>/boards/<board>/cards/<card>/actions/<action_id>.json




