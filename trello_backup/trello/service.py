import re
from typing import Dict, Any, List, Tuple

from pythoncommons.url_utils import UrlUtils

from trello_backup.display.output import MarkdownFormatter
from trello_backup.http_server import HTTP_SERVER_PORT
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
        board, _ = self._get_trello_board_and_lists(name, download_comments=download_comments)
        TrelloApi.download_attachments(board)
        return board

    def _get_trello_board_and_lists(self, name: str, list_names: List[str] = None, download_comments: bool = False) -> Tuple[TrelloBoard, TrelloLists]:
        board_id = self._get_board_id(name)
        board_json = self._get_board_json(board_id)

        # Parse JSON to objects
        trello_lists = TrelloLists(board_json)
        if list_names:
            # TODO Add '*' list filter?
            trello_lists: TrelloLists = trello_lists.filter(list_names)

        trello_checklists = TrelloChecklists(board_json)
        # After this call, TrelloList will contain every card belonging to each list
        trello_cards = TrelloCards(board_json, trello_lists, trello_checklists, download_comments=download_comments)

        board = TrelloBoard(board_id, name, trello_lists.open)
        # Call to fill webpage title and URL
        self._webpage_title_service.process_board_checklist_titles(board)
        self.cache.save()

        return board, trello_lists

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

    def get_lists_and_cards(self, board_name: str, list_names: List[str]) -> List[Dict[str, Any]]:
        board, trello_lists = self._get_trello_board_and_lists(board_name, list_names)
        output_data = self._convert_to_output_data(trello_lists)
        return output_data

    def _convert_to_output_data(self, trello_lists) -> List[Dict[str, Any]]:
        md_formatter = MarkdownFormatter()

        output_data = []
        for list_name, list_obj in trello_lists.by_name.items():
            list_data = {
                "name": list_name,
                "cards": []
            }

            for card in list_obj.cards:
                # Structure the card data, including converting markdown
                card_data = {
                    "id": card.id,
                    "name": card.name,
                    "closed": card.closed,
                    # "description": md_formatter.to_plain_text(card.description),
                    "description": md_formatter.to_plain_text(card.description),
                    "attachments": [
                        {
                            "name": a.name,
                            "url": a.url,
                            "local_path": a.downloaded_file_path,
                            "local_server_path": f"http://localhost:{HTTP_SERVER_PORT}/{a.downloaded_file_path.split('/')[-1]}" if a.downloaded_file_path else ""
                        } for a in card.attachments
                    ],
                    "checklists": [
                        {
                            "name": cl.name,
                            "items": [
                                {"value": cli.value, "url": cli.url, "url_title": cli.url_title, "checked": cli.checked}
                                for cli in cl.items
                            ]
                        } for cl in card.checklists
                    ]
                }
                list_data["cards"].append(card_data)

            output_data.append(list_data)
        return output_data


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