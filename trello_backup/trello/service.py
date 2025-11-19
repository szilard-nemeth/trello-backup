import re
from typing import Dict, Any, List

from pythoncommons.url_utils import UrlUtils

from trello_backup.trello.api import TrelloApi
from trello_backup.trello.cache import WebpageTitleCache
from trello_backup.trello.html import HtmlParser
from trello_backup.trello.model import TrelloChecklist, TrelloBoard, TrelloLists, TrelloChecklists, TrelloCards


class TrelloOperations:
    def __init__(self):
        self._board_name_to_board_id: Dict[str, str] = {}
        self._board_id_to_board_json: Dict[str, Any] = {}
        # Initialize WebpageTitleCache so 'board.get_checklist_url_titles' can use it
        self.cache = WebpageTitleCache()
        self._webpage_title_service = TrelloTitleService(self.cache)

    def get_board(self, name: str, download_comments: bool = False):
        board_id = self._get_board_id(name)
        board_json = self._get_board_json(board_id)

        # Parse JSON to objects
        trello_lists = TrelloLists(board_json)
        trello_checklists = TrelloChecklists(board_json)
        trello_cards = TrelloCards(board_json, trello_lists, trello_checklists, download_comments=download_comments)

        board = TrelloBoard(board_id, name, trello_lists.open)
        self._webpage_title_service.process_board_checklist_titles(board)

        TrelloApi.download_attachments(board)
        return board

    def _get_board_id(self, name):
        if name in self._board_name_to_board_id:
            return self._board_name_to_board_id[name]
        else:
            return TrelloApi.get_board_id(name)

    def _get_board_json(self, board_id):
        if board_id in self._board_id_to_board_json:
            return self._board_id_to_board_json[board_id]
        else:
            return TrelloApi.get_board_details(board_id)

    def get_lists(self, board_name: str, list_names: List[str]):
        board_id = self._get_board_id(board_name)
        board_json = self._get_board_json(board_id)

        trello_lists_all = TrelloLists(board_json)
        trello_lists: TrelloLists = trello_lists_all.filter(list_names)

        trello_checklists = TrelloChecklists(board_json)
        # After this call, TrelloList will contain every card belonging to each list
        trello_cards = TrelloCards(board_json, trello_lists, trello_checklists, download_comments=False)

        board = TrelloBoard(board_id, board_name, trello_lists.open)
        # Call to fill webpage title and URL
        self._webpage_title_service.process_board_checklist_titles(board)

        return trello_lists


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