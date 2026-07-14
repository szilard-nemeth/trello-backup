import json
import unittest
from string import Template
from typing import Dict
from unittest import mock
from unittest.mock import Mock, patch, call, MagicMock

from trello_backup.trello.api import NetworkStatusService, TrelloRepository, OfflineTrelloApi
from trello_backup.trello.filter import CardFilters, ListFilter, TrelloFilters
from trello_backup.trello.model import TrelloChecklist, TrelloBoard, TrelloList, TrelloComment, TrelloLists, \
    TrelloCards, TrelloCard
from trello_backup.trello.service import TrelloOperations, TrelloTitleService, TrelloDataFetcherService, \
    TrelloCleanupService

MOCK_BOARD_ID = "board123"
MOCK_BOARD_NAME = "Test Board"
MOCK_LIST_NAMES = ["List A", "List B"]
MOCK_BOARD_JSON = {"id": MOCK_BOARD_ID, "name": MOCK_BOARD_NAME, "data": "..."}


class MockTrelloLists:
    def __init__(self, lists, is_filtered=False):
        self.by_id = {l.id: l for l in lists}
        self._filtered = is_filtered


class Object(object):
    pass


class TestTrelloOperations(unittest.TestCase):

    CARD_ACTION_RESPONSE_TEMPLATE = Template("""
[ {
  "id" : "dummy_id",
  "idMemberCreator" : "57213e43028b63d18cd5b9f2",
  "data" : {
    "card" : {
      "idList" : "$list_id",
      "id" : "$card_id",
      "name" : "DEX filter for open tasks assigned to me",
      "idShort" : 1201,
      "shortLink" : "arsWJv53"
    },
    "board" : {
      "id" : "616ec99dc34d9d608dc5502b",
      "name" : "CLOUDERA: Weekly Plan",
      "shortLink" : "AZCBY076"
    },
    "text": "$comment"
  },
  "type" : "commentCard",
  "date" : "2023-05-02T19:23:15.431Z",
  "memberCreator" : {
    "id" : "<omitted>",
    "fullName" : "nemethszyszy",
    "username" : "szilard_nemeth"
  }
} ]""")


    @patch('trello_backup.trello.service.TrelloApiAbs')
    def setUp(self, mock_trello_api):
        self.mock_trello_api = mock_trello_api
        # Initialize Mocks for dependencies
        self.mock_cache = Mock()
        self.title_service = TrelloTitleService(self.mock_cache)
        self.mock_data_converter = Mock()
        self.mock_cleanup_service = Mock()

        # Initialize the class under test
        ctx = Object()
        ctx.offline = False
        network_status_service = NetworkStatusService(ctx)
        trello_repository = TrelloRepository(mock_trello_api, OfflineTrelloApi(), network_status_service)

        self._data_fetcher_service = TrelloDataFetcherService(trello_repository, self.title_service, self.mock_data_converter)
        self._trello_ops = TrelloOperations(
            data_fetcher_service=self._data_fetcher_service,
            cleanup_service=self.mock_cleanup_service,
        )

    def test_get_board_names_and_ids(self):
        """Tests that get_board_names_and_ids fetches and stores board info."""
        mock_api_response = {"My Board 1": "id1", "My Board 2": "id2"}
        self.mock_trello_api.list_boards.return_value = mock_api_response

        result = self._trello_ops.get_board_names_and_ids()

        self.mock_trello_api.list_boards.assert_called_once()
        self.assertEqual(result, mock_api_response)
        # Check internal state update
        self.assertEqual(self._data_fetcher_service._board_name_to_board_id, mock_api_response)

    # Patching TrelloApi and Model classes for _get_trello_board_and_lists
    @patch('trello_backup.trello.service.CardFilterer')
    @patch('trello_backup.trello.service.TrelloCards')
    @patch('trello_backup.trello.service.TrelloChecklists')
    @patch('trello_backup.trello.service.TrelloLists')
    @patch('trello_backup.trello.service.TrelloBoard')
    def test_get_trello_board_and_lists_full_flow(self, MockTrelloBoard, MockTrelloLists, MockTrelloChecklists, MockTrelloCards, MockCardFilterer):
        """Tests the full internal flow of fetching and processing board data."""
        # Setup mocks for internal methods
        self._data_fetcher_service._get_board_id = Mock(return_value=MOCK_BOARD_ID)
        self._data_fetcher_service._get_board_json = Mock(return_value=MOCK_BOARD_JSON)

        # Setup mock TrelloLists object
        mock_trello_lists = Mock()
        mock_trello_lists.filter_by_list_names.return_value = mock_trello_lists
        mock_trello_lists.filter_by_list_filter.return_value = mock_trello_lists
        MockTrelloLists.return_value = mock_trello_lists

        # Setup mock TrelloBoard object and its lists
        card1 = Mock(spec=TrelloCard, checklists=[])
        card2 = Mock(spec=TrelloCard, checklists=[])
        mock_trello_list = Mock(spec=TrelloList, cards=[card1, card2]) # A list with some mock cards
        mock_trello_board = Mock(spec=TrelloBoard, lists=[mock_trello_list])
        MockTrelloBoard.return_value = mock_trello_board

        # Setup CardFilterer. These cards are what the real TrelloTitleService will
        # iterate over, so give them an (empty) checklists collection to traverse.
        mock_filtered_cards = [Mock(spec=TrelloCard, checklists=[])]
        MockCardFilterer.filter_cards.return_value = mock_filtered_cards

        # Spy on the real title service so its actual logic runs (e.g. cache.save)
        # while still allowing us to assert how it was called.
        with patch.object(
            self.title_service,
            'process_board_checklist_titles',
            wraps=self.title_service.process_board_checklist_titles,
        ) as spy_process_titles:
            # Call the method under test
            board, trello_lists = self._data_fetcher_service._get_trello_board_and_lists(
                name=MOCK_BOARD_NAME,
                filters=TrelloFilters(MOCK_LIST_NAMES, ListFilter.ALL, CardFilters.ALL)
            )

        # Assertions
        self._data_fetcher_service._get_board_id.assert_called_once_with(MOCK_BOARD_NAME)
        self._data_fetcher_service._get_board_json.assert_called_once_with(MOCK_BOARD_ID)

        MockTrelloLists.assert_called_once_with(MOCK_BOARD_JSON)
        # Assert filtering was called
        mock_trello_lists.filter_by_list_names.assert_called_once_with(MOCK_LIST_NAMES)
        mock_trello_lists.filter_by_list_filter.assert_called_once_with(ListFilter.ALL)

        MockTrelloCards.assert_called_once()
        MockTrelloBoard.assert_called_once()

        # Assert card filtering and list update
        MockCardFilterer.filter_cards.assert_called_once()
        self.assertEqual(mock_trello_list.cards, mock_filtered_cards) # Check if list.cards was overwritten

        # Assert title service was invoked with the board, and that its real logic
        # ran (the real service saves the cache at the end of processing).
        spy_process_titles.assert_called_once_with(mock_trello_board)
        self.mock_cache.save.assert_called_once()

    @patch('trello_backup.trello.service.CardFilterer')
    @patch('trello_backup.trello.service.TrelloCards')
    @patch('trello_backup.trello.service.TrelloChecklists')
    @patch('trello_backup.trello.service.TrelloLists')
    @patch('trello_backup.trello.service.TrelloBoard')
    def test_parse_trello_cards_with_comment_download(self, MockTrelloBoard, MockTrelloLists, MockTrelloChecklists, MockTrelloCards, MockCardFilterer):
        """Tests that comment downloading is triggered when requested."""
        # Setup mock lists and checklists containers
        mock_api_response = {"My Board 1": "id1", "My Board 2": "id2"}
        self.mock_trello_api.list_boards.return_value = mock_api_response

        list_id = "list_id_1"
        def get_actions_for_card_side_effect(card_id):
            json_resp = TestTrelloOperations.CARD_ACTION_RESPONSE_TEMPLATE.substitute(list_id=list_id,
                                                                                      card_id=card_id,
                                                                                      comment=f"Comment for {card_id}")
            return json.loads(json_resp)
        self.mock_trello_api.get_actions_for_card.side_effect = get_actions_for_card_side_effect

        # Mock trello lists / list
        mock_trello_list = MagicMock(spec=TrelloList, id=list_id)
        mock_trello_list.name = "test 1"
        trello_lists = [mock_trello_list]

        mock_trello_lists_instance = mock.MagicMock(spec=TrelloLists)
        mock_trello_lists_instance.by_id: Dict[str, TrelloList] = {l.id: l for l in trello_lists}
        mock_trello_lists_instance.by_name: Dict[str, TrelloList] = {l.name: l for l in trello_lists}
        mock_trello_lists_instance.filter_by_list_names.return_value = mock_trello_lists_instance
        mock_trello_lists_instance.filter_by_list_filter.return_value = mock_trello_lists_instance

        MockTrelloLists.return_value = mock_trello_lists_instance

        # Set up mock TrelloBoard
        mock_trello_board = Mock(spec=TrelloBoard, lists=trello_lists)
        MockTrelloBoard.return_value = mock_trello_board

        # Set up mock TrelloCards
        mock_trello_cards = Mock(spec=TrelloCards, all=[
            MagicMock(id="cardid1", name="card1"),
            MagicMock(id="cardid2", name="card2")])
        MockTrelloCards.return_value = mock_trello_cards


        # Call the method under test
        board, trello_lists = self._data_fetcher_service._get_trello_board_and_lists(
            name=MOCK_BOARD_NAME,
            filters=TrelloFilters(MOCK_LIST_NAMES, ListFilter.ALL, CardFilters.ALL),
            download_comments=True
        )

        for card in mock_trello_cards.all:
            self.assertEqual(1, len(card.comments))
            expected_comment = TrelloComment(id='dummy_id',
                                     author='szilard_nemeth',
                                     date='2023-05-02T19:23:15.431Z',
                                     contents='Comment for ' + card.id)
            self.assertEqual(expected_comment, card.comments[0])


    @patch('trello_backup.trello.service.TrelloApiAbs')
    def test_get_board_id_from_cache(self, MockTrelloApi):
        """Tests getting board ID when it is already in the cache."""
        cached_board_id = "cached_id"
        self._data_fetcher_service._board_name_to_board_id = {MOCK_BOARD_NAME: cached_board_id}

        result = self._data_fetcher_service._get_board_id(MOCK_BOARD_NAME)

        self.assertEqual(result, cached_board_id)
        MockTrelloApi.get_board_id.assert_not_called()

    def test_get_board_id_fetch_and_cache(self):
        """Tests getting board ID when it needs to be fetched and then cached."""
        self.mock_trello_api.get_board_id.return_value = MOCK_BOARD_ID

        result = self._data_fetcher_service._get_board_id(MOCK_BOARD_NAME)

        self.assertEqual(result, MOCK_BOARD_ID)
        self.mock_trello_api.get_board_id.assert_called_once_with(MOCK_BOARD_NAME)
        # Check internal cache update
        self.assertEqual(self._data_fetcher_service._board_name_to_board_id.get(MOCK_BOARD_NAME), MOCK_BOARD_ID)

    @patch('trello_backup.trello.service.TrelloApiAbs')
    def test_get_board_json_from_cache(self, MockTrelloApi):
        """Tests getting board JSON when it is already in the cache."""
        self._data_fetcher_service._board_id_to_board_json = {MOCK_BOARD_ID: MOCK_BOARD_JSON}

        result = self._data_fetcher_service._get_board_json(MOCK_BOARD_ID)

        self.assertEqual(result, MOCK_BOARD_JSON)
        MockTrelloApi.get_board_details.assert_not_called()

    def test_get_board_json_fetch_and_cache(self):
        """Tests getting board JSON when it needs to be fetched and then cached."""
        self.mock_trello_api.get_board_details.return_value = MOCK_BOARD_JSON

        result = self._data_fetcher_service._get_board_json(MOCK_BOARD_ID)

        self.assertEqual(result, MOCK_BOARD_JSON)
        self.mock_trello_api.get_board_details.assert_called_once_with(MOCK_BOARD_ID)
        # Check internal cache update
        self.assertEqual(self._data_fetcher_service._board_id_to_board_json.get(MOCK_BOARD_ID), MOCK_BOARD_JSON)


class TestTrelloTitleService(unittest.TestCase):
    def setUp(self):
        # Initialize Mocks for dependencies
        self.mock_cache = Mock()
        # Initialize the class under test
        self.service = TrelloTitleService(cache=self.mock_cache)

        # Setup basic mock model structure
        self.mock_checklist_item_with_url = Mock(value="http://example.com/item1")
        self.mock_checklist_item_without_url = Mock(value="Just text")
        self.mock_checklist = Mock(
            spec=TrelloChecklist,
            items=[self.mock_checklist_item_with_url, self.mock_checklist_item_without_url]
        )
        self.mock_card = Mock(checklists=[self.mock_checklist])
        self.mock_list = Mock(cards=[self.mock_card])
        self.mock_board = Mock(lists=[self.mock_list])

    # Patching external static methods
    @patch('trello_backup.trello.service.HtmlParser')
    @patch('trello_backup.trello.service.UrlUtils')
    def test_process_checklist_titles_url_found_and_cached(self, MockUrlUtils, MockHtmlParser):
        """Tests fetching title when URL is found and it's NOT in the cache."""
        url = "http://example.com/item1"
        mock_raw_title = "Title \n\t with newline"
        mock_cleaned_title = "Title with newline"

        MockUrlUtils.extract_from_str.side_effect = lambda s: s if s.startswith("http://") else None
        self.mock_cache.get.return_value = None  # Not in cache
        MockHtmlParser.get_title_from_url.return_value = mock_raw_title

        self.service._process_checklist_titles(self.mock_checklist)

        MockUrlUtils.extract_from_str.assert_any_call(self.mock_checklist_item_with_url.value)
        MockUrlUtils.extract_from_str.assert_any_call(self.mock_checklist_item_without_url.value)
        self.mock_cache.get.assert_called_once_with(url)
        MockHtmlParser.get_title_from_url.assert_called_once_with(url)
        # Assert cache interaction
        self.mock_cache.put.assert_called_once_with(url, mock_cleaned_title)
        # Assert model update
        self.mock_checklist.set_url_titles.assert_called_once_with(
            url, mock_cleaned_title, self.mock_checklist_item_with_url
        )

    @patch('trello_backup.trello.service.UrlUtils')
    def test_process_checklist_titles_url_found_in_cache(self, MockUrlUtils):
        """Tests fetching title when URL is found and it IS in the cache."""
        mock_url = "http://example.com/item1"
        mock_cached_title = "Cached Title"

        MockUrlUtils.extract_from_str.side_effect = lambda s: s if s.startswith("http://") else None
        self.mock_cache.get.return_value = mock_cached_title  # Found in cache

        self.service._process_checklist_titles(self.mock_checklist)

        MockUrlUtils.extract_from_str.assert_any_call(self.mock_checklist_item_with_url.value)
        MockUrlUtils.extract_from_str.assert_any_call(self.mock_checklist_item_without_url.value)
        self.mock_cache.get.assert_called_once_with(mock_url)
        # HtmlParser should NOT be called
        self.assertNotIn(call('get_title_from_url'), [c[0] for c in self.mock_cache.method_calls])
        # Cache put should be called to 'clean' the title, even if it's the same
        self.mock_cache.put.assert_not_called() # No put if the title is clean already
        # Assert model update
        self.mock_checklist.set_url_titles.assert_called_once_with(
            mock_url, mock_cached_title, self.mock_checklist_item_with_url
        )

    @patch('trello_backup.trello.service.UrlUtils')
    def test_process_checklist_titles_no_url(self, MockUrlUtils):
        """Tests behavior when no URL is found in the item value."""
        # Force extract_from_str to raise an error for no URL found
        MockUrlUtils.extract_from_str.side_effect = [Exception("No URL"), None] # First item raises, second is None

        self.service._process_checklist_titles(self.mock_checklist)

        # It should attempt to process the first item and fail, and then move to the second
        self.assertEqual(MockUrlUtils.extract_from_str.call_count, 2)
        self.mock_cache.get.assert_not_called()
        self.mock_cache.put.assert_not_called()
        self.mock_checklist.set_url_titles.assert_not_called()


class TestTrelloCleanupServiceRescue(unittest.TestCase):
    """Tests for TrelloCleanupService.rescue_archived_cards."""

    REVIEW_BOARD = {"id": "review123", "shortUrl": "http://trello.com/b/review123"}

    def setUp(self):
        self.mock_api = Mock()
        self.mock_api.create_board.return_value = dict(self.REVIEW_BOARD)
        self.mock_api.get_board_actions.return_value = []

        mock_repository = Mock()
        mock_repository.get_api.return_value = self.mock_api

        self.mock_data_fetcher = Mock()
        self.mock_data_converter = Mock()

        self.service = TrelloCleanupService(
            mock_repository, self.mock_data_fetcher, self.mock_data_converter
        )

        self.board = Mock(spec=TrelloBoard)
        self.board.id = "board123"
        self.board.name = "My Board"

    @staticmethod
    def _make_card(card_id, closed):
        card = Mock(spec=TrelloCard)
        card.id = card_id
        card.closed = closed
        return card

    @staticmethod
    def _make_list(list_id, name, cards):
        trello_list = Mock(spec=TrelloList)
        trello_list.id = list_id
        trello_list.name = name
        trello_list.cards = cards
        return trello_list

    def _set_archived_lists(self, lists):
        trello_lists = Mock()
        trello_lists.get.return_value = lists
        self.mock_data_fetcher.get_lists_and_cards.return_value = (self.board, trello_lists)

    @patch('trello_backup.trello.service.TrelloPrompt')
    def test_rescue_moves_non_empty_lists_and_unarchives_closed_cards(self, MockPrompt):
        MockPrompt.yes_skip_abort.return_value = "y"

        closed_card = self._make_card("cardClosed", closed=True)
        open_card = self._make_card("cardOpen", closed=False)
        non_empty = self._make_list("listA", "List A", [closed_card, open_card])
        empty = self._make_list("listB", "List B", [])
        self._set_archived_lists([non_empty, empty])

        self.service.rescue_archived_cards("My Board", filters=Mock())

        # A review board is created (persistent, timestamped name) and NOT deleted.
        self.mock_api.create_board.assert_called_once()
        created_name = self.mock_api.create_board.call_args.args[0]
        self.assertTrue(created_name.startswith("trello-backup-review-My Board-"))
        self.mock_api.delete_board.assert_not_called()

        # Only the non-empty list is moved and unarchived.
        self.mock_api.move_list_to_board.assert_called_once_with("listA", "review123")
        self.mock_api.set_list_closed.assert_called_once_with("listA", False)

        # Only the archived (closed) card is unarchived; the open one is left alone.
        self.mock_api.set_card_closed.assert_called_once_with("cardClosed", False)

    @patch('trello_backup.trello.service.TrelloPrompt')
    def test_rescue_aborts_when_user_declines(self, MockPrompt):
        MockPrompt.yes_skip_abort.return_value = "s"

        non_empty = self._make_list("listA", "List A", [self._make_card("c1", closed=True)])
        self._set_archived_lists([non_empty])

        self.service.rescue_archived_cards("My Board", filters=Mock())

        MockPrompt.yes_skip_abort.assert_called_once()
        self.mock_api.create_board.assert_not_called()
        self.mock_api.move_list_to_board.assert_not_called()
        self.mock_api.set_card_closed.assert_not_called()

    @patch('trello_backup.trello.service.TrelloPrompt')
    def test_rescue_no_op_when_no_non_empty_lists(self, MockPrompt):
        only_empty = self._make_list("listB", "List B", [])
        self._set_archived_lists([only_empty])

        self.service.rescue_archived_cards("My Board", filters=Mock())

        # Returns before prompting or touching the API.
        MockPrompt.yes_skip_abort.assert_not_called()
        self.mock_api.create_board.assert_not_called()
