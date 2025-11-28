import logging
from typing import List, Dict, Any
from trello_backup.cli.common import TrelloContext
from trello_backup.display.console import CliLogger
from trello_backup.display.output import TrelloCardHtmlGeneratorMode, TrelloListAndCardsPrinter, \
    OutputHandlerFactory, TrelloDataConverter
from trello_backup.trello.filter import CardFilters
from trello_backup.trello.service import TrelloOperations

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)

# TODO IDEA: HTML output file per list,
#  only include: card name (bold), description (plain text), Checklists with check items
#  Add WARNING text if has attachment OR add attachment links

# TODO IDEA add file cache that stores in the following hierarchy:
#  <maindir>/boards/<board>/cards/<card>/actions/<action_id>.json
class MainCommandHandler:
    def __init__(self,
                 ctx: TrelloContext,
                 trello_ops: TrelloOperations,
                 data_converter: TrelloDataConverter,
                 output_factory: OutputHandlerFactory):
        self.ctx = ctx
        self._trello_ops = trello_ops
        self._data_converter = data_converter
        self.output_factory = output_factory

    def backup_board(self, board_name: str,
                     html_gen_config: TrelloCardHtmlGeneratorMode = TrelloCardHtmlGeneratorMode.BASIC):
        card_filters = CardFilters.ALL
        board, _ = self._trello_ops.get_board(board_name, card_filters=card_filters, download_comments=html_gen_config.value.include_comments)
        # TODO ASAP Save trello board json with outputfactory
        # TODO ASAP Make output formats configurable: txt, html, rich, json, ...
        # TODO ASAP use session_dir = ctx.obj[CTX_SESSION_DIR] as output dir
        out = self.output_factory.create_for_board(self._data_converter, board, html_gen_config.value, card_filters)
        out.write_outputs()

    def backup_all_boards(self,
                          html_gen_config: TrelloCardHtmlGeneratorMode = TrelloCardHtmlGeneratorMode.FULL):
        boards: Dict[str, str] = self._trello_ops.get_board_ids_and_names()
        for name in boards.keys():
            self.backup_board(name, html_gen_config=html_gen_config)

    def print_cards(self, board: str, lists: List[str]):
        card_filters = CardFilters.OPEN
        board, trello_lists = self._trello_ops.get_lists_and_cards(board, lists, card_filters)
        trello_data = self._data_converter.convert_to_output_data(trello_lists)
        TrelloListAndCardsPrinter.print_plain_text(trello_data, card_filters, only_open=True)
        # TrelloListAndCardsPrinter.print_rich(trello_data)

