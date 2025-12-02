import logging
from typing import List, Dict, Any
from trello_backup.cli.common import TrelloContext
from trello_backup.display.output import TrelloCardHtmlGeneratorMode, TrelloListAndCardsPrinter, \
    OutputHandlerFactory, TrelloDataConverter, BackupReport
from trello_backup.trello.filter import CardFilters, ListFilter, TrelloFilters
from trello_backup.trello.service import TrelloOperations


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

    def backup_board(self,
                     board_name: str,
                     report: BackupReport,
                     html_gen_config: TrelloCardHtmlGeneratorMode = TrelloCardHtmlGeneratorMode.FULL):
        filters = TrelloFilters.create_default()
        board, _ = self._trello_ops.get_board(board_name, filters=filters, download_comments=html_gen_config.value.include_comments)
        # TODO ASAP Make output formats configurable: txt, html, rich, json, ...
        # TODO ASAP Use OutputType as much as I can
        # TODO ASAP Consider removing this factory?
        out = self.output_factory.create_for_board(self._data_converter, self.ctx.backup_dir, board, html_gen_config.value, filters=filters)
        out.write_outputs(report.file_write_callback)
        return report

    def backup_all_boards(self,
                          report: BackupReport,
                          html_gen_config: TrelloCardHtmlGeneratorMode = TrelloCardHtmlGeneratorMode.FULL):
        boards: Dict[str, str] = self._trello_ops.get_board_names_and_ids()
        for name in boards.keys():
            self.backup_board(name, report, html_gen_config=html_gen_config)
        return report

    def print_cards(self, board: str, filter_list_names: List[str]):
        filters = TrelloFilters(filter_list_names, ListFilter.OPEN, CardFilters.OPEN)
        # TODO ASAP Filtering: Filter should not be passed to TrelloOperations, as it's only a representational concept
        board, trello_lists = self._trello_ops.get_lists_and_cards(board, filters)
        trello_data = self._data_converter.convert_to_output_data(trello_lists)
        TrelloListAndCardsPrinter.print_plain_text(trello_data, print_placeholders=False, only_open=True)
        # TrelloListAndCardsPrinter.print_rich(trello_data)

