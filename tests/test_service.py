import unittest
from unittest.mock import Mock, patch, call
from trello_backup.trello.api import NetworkStatusService, TrelloRepository, TrelloApi, OfflineTrelloApi
from trello_backup.trello.filter import CardFilters, ListFilter
from trello_backup.trello.model import TrelloChecklist, TrelloBoard, TrelloList
from trello_backup.trello.service import TrelloOperations, TrelloTitleService

MOCK_BOARD_ID = "board123"
MOCK_BOARD_NAME = "Test Board"
MOCK_LIST_NAMES = ["List A", "List B"]
MOCK_BOARD_JSON = {"id": MOCK_BOARD_ID, "name": MOCK_BOARD_NAME, "data": "..."}

class Object(object):
    pass


class TestTrelloOperations(unittest.TestCase):
    @patch('trello_backup.trello.service.TrelloApi')
    def setUp(self, mock_trello_api):
        self.mock_trello_api = mock_trello_api
        # Initialize Mocks for dependencies
        self.mock_cache = Mock()
        self.mock_title_service = Mock()
        self.mock_data_converter = Mock()

        # Initialize the class under test
        ctx = Object()
        ctx.offline = False
        network_status_service = NetworkStatusService(ctx)
        trello_repository = TrelloRepository(mock_trello_api, OfflineTrelloApi(), network_status_service)
        self._trello_ops = TrelloOperations(
            trello_repository,
            cache=self.mock_cache,
            title_service=self.mock_title_service,
            data_converter=self.mock_data_converter
        )

    def test_get_board_names_and_ids(self):
        """Tests that get_board_names_and_ids fetches and stores board info."""
        mock_api_response = {"My Board 1": "id1", "My Board 2": "id2"}
        self.mock_trello_api.list_boards.return_value = mock_api_response

        result = self._trello_ops.get_board_names_and_ids()

        self.mock_trello_api.list_boards.assert_called_once()
        self.assertEqual(result, mock_api_response)
        # Check internal state update
        self.assertEqual(self._trello_ops._board_name_to_board_id, mock_api_response)

    # Patching TrelloApi and Model classes for _get_trello_board_and_lists
    @patch('trello_backup.trello.service.CardFilterer')
    @patch('trello_backup.trello.service.TrelloCards')
    @patch('trello_backup.trello.service.TrelloChecklists')
    @patch('trello_backup.trello.service.TrelloLists')
    @patch('trello_backup.trello.service.TrelloBoard')
    def test_get_trello_board_and_lists_full_flow(self, MockTrelloBoard, MockTrelloLists, MockTrelloChecklists, MockTrelloCards, MockCardFilterer):
        """Tests the full internal flow of fetching and processing board data."""
        # Setup mocks for internal methods
        self._trello_ops._get_board_id = Mock(return_value=MOCK_BOARD_ID)
        self._trello_ops._get_board_json = Mock(return_value=MOCK_BOARD_JSON)

        # Setup mock TrelloLists object
        mock_trello_lists = Mock()
        mock_trello_lists.filter_by_list_names.return_value = mock_trello_lists
        mock_trello_lists.filter_by_list_filter.return_value = mock_trello_lists
        MockTrelloLists.return_value = mock_trello_lists

        # Setup mock TrelloBoard object and its lists
        mock_trello_list = Mock(spec=TrelloList, cards=[Mock(), Mock()]) # A list with some mock cards
        mock_trello_board = Mock(spec=TrelloBoard, lists=[mock_trello_list])
        MockTrelloBoard.return_value = mock_trello_board

        # Setup CardFilterer
        mock_filtered_cards = [Mock()]
        MockCardFilterer.filter_cards.return_value = mock_filtered_cards

        # Call the private method
        board, trello_lists = self._trello_ops._get_trello_board_and_lists(
            name=MOCK_BOARD_NAME,
            filter_by_list_names=MOCK_LIST_NAMES,
            card_filters=CardFilters.ALL,
            list_filter=ListFilter.ALL
        )

        # Assertions
        self._trello_ops._get_board_id.assert_called_once_with(MOCK_BOARD_NAME)
        self._trello_ops._get_board_json.assert_called_once_with(MOCK_BOARD_ID)

        MockTrelloLists.assert_called_once_with(MOCK_BOARD_JSON)
        # Assert filtering was called
        mock_trello_lists.filter_by_list_names.assert_called_once_with(MOCK_LIST_NAMES)
        mock_trello_lists.filter_by_list_filter.assert_called_once_with(ListFilter.ALL)

        MockTrelloCards.assert_called_once()
        MockTrelloBoard.assert_called_once()

        # Assert card filtering and list update
        MockCardFilterer.filter_cards.assert_called_once()
        self.assertEqual(mock_trello_list.cards, mock_filtered_cards) # Check if list.cards was overwritten

        # Assert title service and cache calls
        self.mock_title_service.process_board_checklist_titles.assert_called_once_with(mock_trello_board)
        self.mock_cache.save.assert_called_once()

    @patch('trello_backup.trello.service.TrelloApi')
    def test_get_board_id_from_cache(self, MockTrelloApi):
        """Tests getting board ID when it is already in the cache."""
        cached_board_id = "cached_id"
        self._trello_ops._board_name_to_board_id = {MOCK_BOARD_NAME: cached_board_id}

        result = self._trello_ops._get_board_id(MOCK_BOARD_NAME)

        self.assertEqual(result, cached_board_id)
        MockTrelloApi.get_board_id.assert_not_called()

    def test_get_board_id_fetch_and_cache(self):
        """Tests getting board ID when it needs to be fetched and then cached."""
        self.mock_trello_api.get_board_id.return_value = MOCK_BOARD_ID

        result = self._trello_ops._get_board_id(MOCK_BOARD_NAME)

        self.assertEqual(result, MOCK_BOARD_ID)
        self.mock_trello_api.get_board_id.assert_called_once_with(MOCK_BOARD_NAME)
        # Check internal cache update
        self.assertEqual(self._trello_ops._board_name_to_board_id.get(MOCK_BOARD_NAME), MOCK_BOARD_ID)

    @patch('trello_backup.trello.service.TrelloApi')
    def test_get_board_json_from_cache(self, MockTrelloApi):
        """Tests getting board JSON when it is already in the cache."""
        self._trello_ops._board_id_to_board_json = {MOCK_BOARD_ID: MOCK_BOARD_JSON}

        result = self._trello_ops._get_board_json(MOCK_BOARD_ID)

        self.assertEqual(result, MOCK_BOARD_JSON)
        MockTrelloApi.get_board_details.assert_not_called()

    def test_get_board_json_fetch_and_cache(self):
        """Tests getting board JSON when it needs to be fetched and then cached."""
        self.mock_trello_api.get_board_details.return_value = MOCK_BOARD_JSON

        result = self._trello_ops._get_board_json(MOCK_BOARD_ID)

        self.assertEqual(result, MOCK_BOARD_JSON)
        self.mock_trello_api.get_board_details.assert_called_once_with(MOCK_BOARD_ID)
        # Check internal cache update
        self.assertEqual(self._trello_ops._board_id_to_board_json.get(MOCK_BOARD_ID), MOCK_BOARD_JSON)


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
