import logging
import re
from typing import Dict, Any, List, Tuple, Optional

from pythoncommons.url_utils import UrlUtils

from trello_backup.cli.prompt import TrelloPrompt
from trello_backup.display.console import CliLogger
from trello_backup.display.output import MarkdownFormatter, TrelloDataConverter, TrelloListAndCardsPrinter
from trello_backup.http_server import HTTP_SERVER_PORT
from trello_backup.trello.api import TrelloApi, TrelloApiAbs, TrelloRepository
from trello_backup.trello.cache import WebpageTitleCache
from trello_backup.trello.filter import CardFilters, CardFilterer, ListFilter, TrelloFilters
from trello_backup.trello.html import HtmlParser
from trello_backup.trello.model import TrelloChecklist, TrelloBoard, TrelloLists, TrelloChecklists, TrelloCards, \
    TrelloComment
from trello_backup.trello.parser import TrelloObjectParser

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


class TrelloOperations:
    def __init__(self,
                 trello_repository: TrelloRepository,
                 cache: WebpageTitleCache,
                 title_service: 'TrelloTitleService',
                 data_converter: TrelloDataConverter):
        self._api: TrelloApiAbs = trello_repository.get_api()
        self._board_name_to_board_id: Dict[str, str] = {}
        self._board_id_to_board_json: Dict[str, Any] = {}
        self._cache = cache
        self._webpage_title_service = title_service
        self._data_converter = data_converter

    def get_board_names_and_ids(self):
        d = self._api.list_boards()
        for board_name, board_id in d.items():
            self._board_name_to_board_id[board_name] = board_id
        return d

    # TODO ASAP Refactor, unify interface: get_board + get_lists_and_cards
    def get_board(self, name: str,
                  filters: TrelloFilters,
                  download_comments: bool = False) -> Tuple[TrelloBoard, Optional[TrelloLists]]:
        board, _ = self._get_trello_board_and_lists(name,
                                                    filters,
                                                    download_comments=download_comments)
        self._api.download_attachments(board)
        return board, None

    def get_lists_and_cards(self,
                            board_name: str,
                            filters: TrelloFilters) -> Tuple[TrelloBoard, TrelloLists]:
        board, trello_lists = self._get_trello_board_and_lists(board_name, filters)
        # TODO ASAP Refactor, does it make sense to return trello_lists
        return board, trello_lists


    def _get_trello_board_and_lists(self,
                                    name: str,
                                    filters: TrelloFilters,
                                    download_comments: bool = False) -> Tuple[TrelloBoard, TrelloLists]:
        # TODO ASAP Print processing board, similar to "Processing card...)
        board_id = self._get_board_id(name)
        board_json = self._get_board_json(board_id)

        # Parse JSON to objects
        trello_lists = TrelloLists(board_json)
        # TODO ASAP Filtering: This should be more transparently filtered
        if filters.filter_list_names:
            trello_lists = trello_lists.filter_by_list_names(filters.filter_list_names)
        if filters.list_filter:
            trello_lists = trello_lists.filter_by_list_filter(filters.list_filter)

        trello_checklists = TrelloChecklists(board_json)
        # After this call, TrelloList will contain every card belonging to each list

        trello_cards = TrelloCards(board_json, trello_lists, trello_checklists)
        if download_comments:
            self._fetch_comments_for_cards(download_comments, trello_cards)

        board = TrelloBoard(board_id, board_json, name, trello_lists.get())
        for list in board.lists:
            filtered_cards = CardFilterer.filter_cards(list, filters.card_filters)
            # Overwrite list.cards
            list.cards = filtered_cards

        # Call to fill webpage title and URL
        self._webpage_title_service.process_board_checklist_titles(board)
        self._cache.save()

        # TODO ASAP Refactor, does it make sense to return trello_lists
        return board, trello_lists

    def _fetch_comments_for_cards(self, download_comments: bool, trello_cards: TrelloCards):
        for card in trello_cards.all:
            if download_comments:
                actions_resp_parsed = self._api.get_actions_for_card(card.id)
                comments: List[TrelloComment] = TrelloObjectParser.parse_comments_for_card(card, actions_resp_parsed)
                card.comments = comments

    def _get_board_id(self, name):
        board_id = self._board_name_to_board_id.get(name)
        if board_id is None:
            board_id = self._api.get_board_id(name)
            self._board_name_to_board_id[name] = board_id
        return board_id

    def _get_board_json(self, board_id):
        board_json = self._board_id_to_board_json.get(board_id)
        if board_json is None:
            board_json = self._api.get_board_details(board_id)
            self._board_id_to_board_json[board_id] = board_json
        return board_json

    def cleanup_board(self,
                      board_name: str,
                      filters: TrelloFilters):
        def _yes_handler():
            CLI_LOG.info(f"Deleting card: {card['name']}")
            self._api.delete_card(card["id"])
            return "DELETED"
        def _no_handler():
            return "SKIPPED"
        def _abort_handler():
            return "ABORTED"

        CLI_LOG.info(f"Starting cleanup for board: {board_name}")
        board, trello_lists = self.get_lists_and_cards(board_name, filters)
        trello_data = self._data_converter.convert_to_output_data(trello_lists)
        num_lists = len(trello_data)
        for idx, list_obj in enumerate(trello_data):
            res = TrelloPrompt.prompt_ask(f"Proceed cleanup with list '{list_obj['name']}'", default=True)
            if not res:
                CLI_LOG.info("Cleanup aborted by user")
                return
            CLI_LOG.info(f"Starting cleanup for list: {list_obj['name']}")
            l_idx_info = f"[{idx+1}/{num_lists}]"
            CLI_LOG.info(f"{l_idx_info} Actual list: {list_obj['name']}")
            num_cards = len(list_obj["cards"])

            for idx, card in enumerate(list_obj["cards"]):
                c_idx_info = f"[{idx+1}/{num_cards}]"
                TrelloListAndCardsPrinter.print_card_plain_text(card, print_placeholders=True)
                card_info = f"Board: {board.name}, List: {list_obj['name']}"
                CLI_LOG.info(f"{c_idx_info} Actual card: %s (%s)", card['name'], card_info)
                res = TrelloPrompt.choices_yes_no_abort("OK to remove card?",
                                                        on_yes=_yes_handler,
                                                        on_no=_no_handler,
                                                        on_abort=_abort_handler)
                if res == "ABORTED":
                    CLI_LOG.info("Cleanup aborted by user")
                    return



class TrelloTitleService:
    """
    Handles the responsibility of fetching and caching web page titles for
    Trello checklist items, decoupling this logic from the data models.
    """
    def __init__(self, cache: WebpageTitleCache):
        # The service holds the cache dependency
        self._cache = cache

    def process_board_checklist_titles(self, board: 'TrelloBoard'):
        """
        Iterates through all checklists in a board to fetch and cache URL titles.
        """
        # Ensure the cache is used with a context manager if possible, or managed externally
        # to ensure it saves/closes correctly.

        for trello_list in board.lists:
            for card in trello_list.cards:
                for checklist in card.checklists:
                    self._process_checklist_titles(checklist)

        # After processing, ensure the cache is saved
        self._cache.save()

    def _process_checklist_titles(self, checklist: 'TrelloChecklist'):
        for item in checklist.items:
            try:
                # 1. Identify URL
                url = UrlUtils.extract_from_str(item.value)
            except:
                url = None

            if url:
                # 2. Get from cache or fetch (ALL cache interaction is here)
                url_title = self._cache.get(url)
                if not url_title:
                    # Fetch title of URL
                    url_title = HtmlParser.get_title_from_url(url)
                    url_title = re.sub(r'[\n\t\r]+', ' ', url_title)
                    # Replace only two or more consecutive spaces with a single space
                    url_title = re.sub(r' {2,}', ' ', url_title)

                    if url_title:
                        # Put title into cache
                        self._cache.put(url, url_title)
                else:
                    # Read from cache (still need to clean old titles if needed)
                    new_url_title = re.sub(r'[\n\t\r]+', ' ', url_title)
                    if url_title != new_url_title:
                        self._cache.put(url, new_url_title)
                    url_title = new_url_title

                if not url_title:
                    url_title = url

                # 3. Update the model object
                checklist.set_url_titles(url, url_title, item)