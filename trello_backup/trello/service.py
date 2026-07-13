import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

from pythoncommons.url_utils import UrlUtils
from rich import box
from rich.table import Table

from trello_backup.cli.prompt import TrelloPrompt
from trello_backup.display.console import CliLogger
from trello_backup.display.output import TrelloDataConverter, TrelloListAndCardsPrinter
from trello_backup.trello.api import TrelloApiAbs, TrelloRepository
from trello_backup.trello.cache import WebpageTitleCache
from trello_backup.trello.filter import CardFilterer, TrelloFilters, ListFilter, CardFilters
from trello_backup.trello.html import HtmlParser
from trello_backup.trello.model import TrelloChecklist, TrelloBoard, TrelloList, TrelloLists, TrelloChecklists, \
    TrelloCards, TrelloComment
from trello_backup.trello.parser import TrelloObjectParser

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


class TrelloOperations:
    def __init__(self,
                 data_fetcher_service: 'TrelloDataFetcherService',
                 cleanup_service: 'TrelloCleanupService'):
        self._data_fetcher_service = data_fetcher_service
        self._cleanup_service = cleanup_service

    def get_board_names_and_ids(self):
        return self._data_fetcher_service.get_board_names_and_ids()

    def get_board(self, name: str,
                  filters: TrelloFilters,
                  download_comments: bool = False) -> Tuple[TrelloBoard, Optional[TrelloLists]]:
        return self._data_fetcher_service.get_board(name, filters, download_comments)

    def get_lists_and_cards(self,
                            board_name: str,
                            filters: TrelloFilters) -> Tuple[TrelloBoard, TrelloLists]:
        return self._data_fetcher_service.get_lists_and_cards(board_name, filters)

    def cleanup_board(self,
                      board_name: str,
                      filters: TrelloFilters,
                      batch_mode: bool,
                      cleanup_archived_lists: bool):
        if cleanup_archived_lists:
            if filters.filter_list_names:
                CLI_LOG.warning(
                    "Ignoring --filter-list %s: it is not supported together with "
                    "--cleanup-archived-lists",
                    filters.filter_list_names,
                )
            archived_filters = TrelloFilters([], ListFilter.CLOSED, CardFilters.ALL)
            self._cleanup_service.cleanup_archived_lists(board_name, archived_filters)
        else:
            self._cleanup_service.interactive_cleanup(board_name, filters, batch_mode)

    def get_cards_by_links(self, card_links: List[str]):
        self._data_fetcher_service.get_cards_by_links(card_links)


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

    def process_cards_checklist_titles(self, cards: List['TrelloCard']):
        """
        Iterates through all cards then fetches and caches URL titles.
        """
        # Ensure the cache is used with a context manager if possible, or managed externally
        # to ensure it saves/closes correctly.
        for card in cards:
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
                # Uncomment to delete from cache
                # del self._cache._shelf["https://chatgpt.com/c/6872d253-faf8-8007-8ad8-6c144b31ce50"]
                url_title = self._cache.get(url)
                if not url_title:
                    # Fetch title of URL
                    url_title = HtmlParser.get_title_from_url(url)
                    if url_title:
                        url_title = self._process_fetched_url_title(url, url_title)
                else:
                    # Read from cache (still need to clean old titles if needed)
                    new_url_title = re.sub(r'[\n\t\r]+', ' ', url_title)
                    if url_title != new_url_title:
                        self._cache.put(url, new_url_title)
                    url_title = new_url_title

                # 3. Update the model object
                if url == url_title:
                    # If cache says webpage title is equal to URL, simply ignore and set None
                    url_title = None
                checklist.set_url_titles(url, url_title, item)

    def _process_fetched_url_title(self, url: str | Any, url_title: str | None) -> str:
        url_title = re.sub(r'[\n\t\r]+', ' ', url_title)
        # Replace only two or more consecutive spaces with a single space
        url_title = re.sub(r' {2,}', ' ', url_title)

        if url_title:
            # Put title into cache
            self._cache.put(url, url_title)
        return url_title


class TrelloDataFetcherService:
    def __init__(self,
                 trello_repository: TrelloRepository,
                 title_service: TrelloTitleService,
                 data_converter: TrelloDataConverter):
        self._api: TrelloApiAbs = trello_repository.get_api()
        self._webpage_title_service = title_service
        self._data_converter = data_converter
        self._board_name_to_board_id: Dict[str, str] = {}
        self._board_id_to_board_json: Dict[str, Any] = {}

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

    def get_board_names_and_ids(self):
        d = self._api.list_boards()
        for board_name, board_id in d.items():
            self._board_name_to_board_id[board_name] = board_id
        return d

    def get_lists_and_cards(self,
                            board_name: str,
                            filters: TrelloFilters) -> Tuple[TrelloBoard, TrelloLists]:
        # TODO ASAP Refactor, does it make sense to return trello_lists
        board, trello_lists = self._get_trello_board_and_lists(board_name, filters)
        return board, trello_lists

    def get_board(self,
                  name: str,
                  filters: TrelloFilters,
                  download_comments: bool = False) -> Tuple[TrelloBoard, Optional[TrelloLists]]:
        # TODO ASAP Refactor, unify interface: get_board + get_lists_and_cards
        board, _ = self._get_trello_board_and_lists(name,
                                                    filters,
                                                    download_comments=download_comments)
        self._api.download_attachments(board)
        return board, None

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

        # TODO ASAP Refactor, does it make sense to return trello_lists
        return board, trello_lists

    def get_cards_by_links(self,
                           card_links: List[str]):
        # TODO ASAP Should download attachments to temporary directory
        """
        Here we don't work with the board json response, we only download the specified cards for optimal speed.
        For each card, the checklist and the list is also fetched.
        Then we create a board dict object with keys: 'cards', 'lists' and 'checklists'.
        Parsing logic could belong to TrelloObjectParser, but we also need API calls to fetch data, so we keep the logic here.
        :param card_links:
        :return:
        """
        lists = []
        cards = []
        checklists = []
        for card_link in card_links:
            card_json = self._api.download_card_by_share_link(card_link)
            cards.append(card_json)
            for checklist_id in card_json["idChecklists"]:
                checklist_data = self._api.get_checklist_by_id(checklist_id)
                checklists.append(checklist_data)
            list_data = self._api.get_list_by_id(card_json["idList"])
            lists.append(list_data)

        board_dict = {"cards": cards, "lists": lists, "checklists": checklists}
        trello_lists = TrelloLists(board_dict)
        trello_checklists = TrelloChecklists(board_dict)
        trello_cards = TrelloCards(board_dict,
                                   trello_lists,
                                   trello_checklists)

        # Call to fill webpage title and URL
        self._webpage_title_service.process_cards_checklist_titles(trello_cards.all)

        trello_data = self._data_converter.convert_to_output_data(trello_lists)
        for idx, list_obj in enumerate(trello_data):
            for idx, card in enumerate(list_obj["cards"]):
                TrelloListAndCardsPrinter.print_card_plain_text(card, print_placeholders=True)

    def _fetch_comments_for_cards(self, download_comments: bool, trello_cards: TrelloCards):
        for card in trello_cards.all:
            if download_comments:
                actions_resp_parsed = self._api.get_actions_for_card(card.id)
                comments: List[TrelloComment] = TrelloObjectParser.parse_comments_for_card(card, actions_resp_parsed)
                card.comments = comments


class TrelloCleanupService:
    def __init__(self,
                 trello_repository: TrelloRepository,
                 data_fetcher_service: TrelloDataFetcherService,
                 data_converter: TrelloDataConverter):
        self._api: TrelloApiAbs = trello_repository.get_api()
        self._data_converter = data_converter
        self._data_fetcher_service = data_fetcher_service

    def interactive_cleanup(self,
                            board_name: str,
                            filters: TrelloFilters,
                            batch_mode: bool):
        additional_log = ", Batch mode is enabled" if batch_mode else ""
        CLI_LOG.info(f"Starting cleanup for board: {board_name}{additional_log}")
        # TODO here, archived lists can be removed (only if they don't have associated cards)
        # TODO here, open cards with archived lists can be moved to a temporary list
        board, trello_lists = self._data_fetcher_service.get_lists_and_cards(board_name, filters)
        trello_data = self._data_converter.convert_to_output_data(trello_lists)
        num_lists = len(trello_data)
        list_names = [l["name"] for l in trello_data]
        CLI_LOG.info("Processing lists in this order: %s", list_names)
        for idx, list_obj in enumerate(trello_data):
            list_name = list_obj['name']
            res = TrelloPrompt.yes_skip_abort(f"Proceed cleanup with list '{list_name}'")
            if res == "y":
                CLI_LOG.info(f"Cleaning up list: {list_name}")
            elif res == "a":
                CLI_LOG.info("Cleanup aborted by user")
                return
            elif res == "s":
                continue
            CLI_LOG.info(f"Starting cleanup for list: {list_name}")
            l_idx_info = f"[{idx+1}/{num_lists}]"
            CLI_LOG.info(f"{l_idx_info} Actual list: {list_name}")
            num_cards = len(list_obj["cards"])

            if batch_mode:
                self._batch_delete_cards(board, list_name, list_obj, num_cards)
            else:
                ret = self._interactive_delete_cards(board, list_name, list_obj, num_cards)
                if not ret:
                    # Aborted
                    return
            # TODO ASAP Ask to remove list if all cards have been removed

    def _batch_delete_cards(self, board: TrelloBoard, list_name, list_obj: dict[str, Any], num_cards: int):
        for idx, card in enumerate(list_obj["cards"]):
            c_idx_info = f"[{idx + 1}/{num_cards}]"
            card_info = f"Board: {board.name}, List: {list_name}"
            CLI_LOG.info(f"{c_idx_info} Card: %s (%s)", card['name'], card_info)
            TrelloListAndCardsPrinter.print_card_plain_text(card, print_placeholders=True)
        resp = TrelloPrompt.prompt_ask(f"OK to delete all cards ({len(list_obj["cards"])}) in list?")
        if resp:
            card_names = [c['name'] for c in list_obj["cards"]]
            card_ids = [c['id'] for c in list_obj["cards"]]
            CLI_LOG.info(f"Deleting all cards: {card_names}")
            for c_id in card_ids:
                self._api.delete_card(c_id)

    def cleanup_archived_lists(self, board_name, filters):
        CLI_LOG.info(f"Starting cleanup of archived lists for board: {board_name}")
        board, trello_lists = self._data_fetcher_service.get_lists_and_cards(board_name, filters)

        # 'trello_lists' is already filtered down to the archived (closed) lists.
        archived_lists = trello_lists.get()

        # The command only removes *empty* archived lists. Purging a list is
        # permanent and also destroys any cards it contains (see _purge_lists),
        # so archived lists that still have cards are skipped to avoid data loss.
        empty_lists = [l for l in archived_lists if not l.cards]
        non_empty_names = [l.name for l in archived_lists if l.cards]
        if non_empty_names:
            CLI_LOG.warning("Skipping non-empty archived lists: %s", non_empty_names)

        if not empty_lists:
            CLI_LOG.info("No empty archived lists to clean up on board: %s", board_name)
            return

        # Log the candidate lists (name + archive date) to the CLI separately from
        # the confirmation prompt, so there is a persistent record of exactly what
        # is about to be removed.
        CLI_LOG.info("Found %d empty archived list(s) to clean up:", len(empty_lists))
        CLI_LOG.info("Fetching archive dates from the board's action history, this may take a while...")
        archive_dates = self._get_list_archive_dates(board)
        self._print_archived_lists_table(empty_lists, archive_dates)

        list_names_and_ids = [(l.name, l.id) for l in empty_lists]
        res = TrelloPrompt.yes_skip_abort(
            f"Permanently delete {len(list_names_and_ids)} empty archived list(s)?"
        )
        if res != "y":
            CLI_LOG.info("Archived list cleanup skipped/aborted by user")
            return

        self._purge_lists(board, list_names_and_ids)

    @staticmethod
    def _created_date_from_id(object_id: str) -> str:
        """
        Returns the creation date (ISO 8601, UTC) encoded in a Trello object id.

        Trello ids are MongoDB ObjectIds whose first 4 bytes (first 8 hex chars)
        are the Unix creation timestamp, so every list exposes a reliable creation
        date without any extra API calls.
        """
        try:
            ts = int(object_id[:8], 16)
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (ValueError, TypeError, IndexError):
            return "unknown"

    def _get_list_archive_dates(self, board: TrelloBoard) -> Dict[str, str]:
        """
        Best-effort mapping of list id -> the date it was most recently archived,
        derived from the board's 'updateList' action history. Trello does not expose
        an archive timestamp on the list object itself. The full action history is
        paged through, so this is complete unless the archive event has aged out of
        Trello's retained actions entirely.
        """
        archive_dates: Dict[str, str] = {}
        actions = self._api.get_board_actions(board.id, action_filter="updateList")
        # Actions are returned newest-first, so the first archive action seen for a
        # given list is the most recent one.
        for action in actions:
            data = action.get("data", {})
            # A list was archived when its 'closed' flag changed from False to True.
            if data.get("old", {}).get("closed") is False:
                list_id = data.get("list", {}).get("id")
                if list_id and list_id not in archive_dates:
                    archive_dates[list_id] = action.get("date", "unknown")
        return archive_dates

    def _print_archived_lists_table(self, lists: List[TrelloList], archive_dates: Dict[str, str]):
        rows = [
            (l.name, l.id, self._created_date_from_id(l.id), archive_dates.get(l.id, "unknown"))
            for l in lists
        ]

        # Order by archive date (desc). Lists whose archive date is unknown are
        # grouped last and ordered among themselves by creation date (desc).
        def sort_key(row: Tuple[str, str, str, str]):
            _, _, created, archived = row
            archived_known = archived != "unknown"
            return archived_known, archived if archived_known else "", created

        rows.sort(key=sort_key, reverse=True)

        table = Table(title="Empty archived lists to clean up", show_lines=True, box=box.SQUARE)
        table.add_column("#", justify="right")
        table.add_column("List name")
        table.add_column("List ID")
        table.add_column("Created on")
        table.add_column("Archived on")
        for idx, (name, list_id, created, archived) in enumerate(rows, start=1):
            table.add_row(str(idx), name, list_id, created, archived)

        CLI_LOG.print(table)

    def _purge_lists(self, board: TrelloBoard, list_names_and_ids: List[Tuple[str, str]]):
        # Trello's REST API cannot delete a list directly; it can only archive one.
        # The supported workaround for permanent removal is to move the lists onto a
        # throwaway board and then delete that entire board, which permanently
        # removes the board along with all lists and cards it contains.
        trash_board_name = f"trello-backup-trash-{board.name}"
        CLI_LOG.info("Creating temporary trash board: %s", trash_board_name)
        trash_board = self._api.create_board(trash_board_name)
        trash_board_id = trash_board["id"]
        trash_board_url = trash_board.get("shortUrl") or trash_board.get("url")

        try:
            # Move the lists to the trash board and unarchive them there so the user
            # can visually review the (previously archived) lists before deletion.
            for l_name, l_id in list_names_and_ids:
                CLI_LOG.info("Moving archived list '%s' (id=%s) to trash board", l_name, l_id)
                self._api.move_list_to_board(l_id, trash_board_id)
                self._api.set_list_closed(l_id, False)

            res = TrelloPrompt.yes_skip_abort(
                f"Moved {len(list_names_and_ids)} list(s) to trash board '{trash_board_name}' "
                f"({trash_board_url}) and unarchived them for review. "
                f"Permanently delete the trash board and all of these lists?"
            )
            if res == "y":
                CLI_LOG.info("Permanently deleting trash board '%s' (id=%s)", trash_board_name, trash_board_id)
                self._api.delete_board(trash_board_id)
                CLI_LOG.info("Successfully purged %d archived list(s)", len(list_names_and_ids))
                return

            # User declined: restore the lists to their original board and re-archive
            # them, then remove the now-empty trash board so nothing is left behind.
            CLI_LOG.info(
                "Deletion declined; restoring %d list(s) to board '%s' and re-archiving them",
                len(list_names_and_ids), board.name,
            )
            for l_name, l_id in list_names_and_ids:
                self._api.move_list_to_board(l_id, board.id)
                self._api.set_list_closed(l_id, True)
            self._api.delete_board(trash_board_id)
            CLI_LOG.info("Restored %d list(s) to their original archived state", len(list_names_and_ids))
        except Exception:
            CLI_LOG.error(
                "Error while purging archived lists. Manually inspect/clean up trash board "
                "'%s' (id=%s): %s",
                trash_board_name, trash_board_id, trash_board_url,
            )
            raise

    def _interactive_delete_cards(self, board: TrelloBoard, list_name, list_obj: dict[str, Any], num_cards: int):
        for idx, card in enumerate(list_obj["cards"]):
            c_idx_info = f"[{idx+1}/{num_cards}]"
            TrelloListAndCardsPrinter.print_card_plain_text(card, print_placeholders=True)
            card_info = f"Board: {board.name}, List: {list_name}"
            CLI_LOG.info(f"{c_idx_info} Actual card: %s (%s)", card['name'], card_info)
            res = TrelloPrompt.yes_no_abort("OK to delete card?")
            if res == "y":
                CLI_LOG.info(f"Deleting card: {card['name']}")
                self._api.delete_card(card["id"])
            if res == "a":
                CLI_LOG.info("Cleanup aborted by user")
                return False
        return True