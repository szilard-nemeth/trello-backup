import unittest
from typing import List
from unittest.mock import MagicMock, patch

from tests.test_utils import TestUtils
from trello_backup.trello.model import TrelloList, TrelloCard, TrelloLists, TrelloChecklistItem, TrelloBoard


# Mocking the external dependency 'trello_backup.trello.parser'
# We create a placeholder class for the imported types
class MockTrelloObjectParser:
    @staticmethod
    def parse_trello_lists(board_json) -> List[TrelloList]:
        """Mock implementation for TrelloLists tests."""
        # This will be replaced by the patch decorator in the tests
        pass

tu = TestUtils

class TestTrelloCard(unittest.TestCase):
    """Tests for the properties and methods of the TrelloCard class."""

    def setUp(self):
        # Setup mock dependencies for TrelloCard
        self.mock_list = MagicMock()
        self.mock_attachment = MagicMock()
        self.mock_checklist = MagicMock()

    def test_open_card_property(self):
        card = TrelloCard(
            id='1', name='Test', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[], checklists=[], labels=[], closed=False, comments=[], due_date="", activities=[]
        )
        self.assertTrue(card.open)

    def test_closed_card_property(self):
        card = TrelloCard(
            id='1', name='Test', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[], checklists=[], labels=[], closed=True, comments=[], due_date="", activities=[]
        )
        self.assertFalse(card.open)

    def test_has_description_property(self):
        card_with = TrelloCard(
            id='1', name='Test', short_url=tu.generate_short_url(), list=self.mock_list, description='A description',
            attachments=[], checklists=[], labels=[], closed=False, comments=[], due_date="", activities=[]
        )
        card_without = TrelloCard(
            id='2', name='Test2', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[], checklists=[], labels=[], closed=False, comments=[], due_date="", activities=[]
        )
        self.assertTrue(card_with.has_description)
        self.assertFalse(card_without.has_description)

    def test_has_checklist_property(self):
        card_with = TrelloCard(
            id='1', name='Test', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[], checklists=[self.mock_checklist], labels=[], closed=False, comments=[], due_date="", activities=[]
        )
        card_without = TrelloCard(
            id='2', name='Test2', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[], checklists=[], labels=[], closed=False, comments=[], due_date="", activities=[]
        )
        self.assertTrue(card_with.has_checklist)
        self.assertFalse(card_without.has_checklist)

    def test_has_attachments_property(self):
        card_with = TrelloCard(
            id='1', name='Test', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[self.mock_attachment], checklists=[], labels=[], closed=False, comments=[], due_date="", activities=[]
        )
        card_without = TrelloCard(
            id='2', name='Test2', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[], checklists=[], labels=[], closed=False, comments=[], due_date="", activities=[]
        )
        self.assertTrue(card_with.has_attachments)
        self.assertFalse(card_without.has_attachments)

    def test_get_labels_as_str_single_label(self):
        labels = ["Bug"]
        card = TrelloCard(
            id='1', name='Test', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[], checklists=[], labels=labels, closed=False, comments=[], due_date="", activities=[]
        )
        self.assertEqual(card.get_labels_as_str(), "Bug")

    def test_get_labels_as_str_multiple_labels(self):
        labels = ["Feature", "Critical", "Urgent"]
        card = TrelloCard(
            id='1', name='Test', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[], checklists=[], labels=labels, closed=False, comments=[], due_date="", activities=[]
        )
        self.assertEqual(card.get_labels_as_str(), "Feature, Critical, Urgent")

    def test_get_labels_as_str_no_labels(self):
        labels = []
        card = TrelloCard(
            id='1', name='Test', short_url=tu.generate_short_url(), list=self.mock_list, description='',
            attachments=[], checklists=[], labels=labels, closed=False, comments=[], due_date="", activities=[]
        )
        self.assertEqual(card.get_labels_as_str(), "")

class TestTrelloLists(unittest.TestCase):
    """Tests for the TrelloLists initialization and filter method."""

    @patch('trello_backup.trello.parser.TrelloObjectParser')
    def setUp(self, mock_parser_cls):
        self.mock_board_json = {"id": "board_1"}
        self.list_a = TrelloList(closed=False, id='101', name='To Do', board_id='board_1', pos=11111)
        self.list_b = TrelloList(closed=False, id='102', name='In Progress', board_id='board_1', pos=22222)
        self.list_c = TrelloList(closed=True, id='103', name='Done (Closed)', board_id='board_1', pos=33333)
        self.all_lists = [self.list_a, self.list_b, self.list_c]

        # Set the side_effect for the mocked parser method
        # MockTrelloObjectParser.parse_trello_lists = MagicMock(return_value=self.all_lists)

        # # Patch the specific method to return your mock data
        # with patch('trello_backup.trello.parser.TrelloObjectParser.parse_trello_lists') as mock_parser_func:
        #     mock_parser_func.return_value = self.all_lists
        #     # Initialize the instance inside the patch context
        #     self.trello_lists = TrelloLists(self.mock_board_json)

        # Configure the mocked class's method to return the expected data
        # This configuration will now apply to *all* calls to the parser within the class.
        mock_parser_cls.parse_trello_lists.return_value = self.all_lists

        # Initialize the instance for testing
        self.trello_lists = TrelloLists(self.mock_board_json)

    def test_get_by_id(self):
        self.assertEqual(self.trello_lists._by_id['101'], self.list_a)
        self.assertEqual(len(self.trello_lists._by_id), 3)

    def test_get_by_name(self):
        self.assertEqual(self.trello_lists._by_name['To Do'], self.list_a)
        self.assertEqual(len(self.trello_lists._by_name), 3)

    def test_get_open_lists(self):
        # Should only include 'To Do' and 'In Progress'
        self.assertEqual(len(self.trello_lists.open), 2)
        self.assertIn(self.list_a, self.trello_lists.open)
        self.assertIn(self.list_b, self.trello_lists.open)
        self.assertNotIn(self.list_c, self.trello_lists.open)

    @patch('trello_backup.trello.parser.TrelloObjectParser')
    def test_filter_success(self, mock_parser_cls):
        mock_parser_cls.parse_trello_lists.return_value = self.all_lists

        filter_names = ['To Do', 'Done (Closed)']
        filtered_lists = self.trello_lists.filter_by_list_names(filter_names)

        self.assertIsInstance(filtered_lists, TrelloLists)
        # Check that the new instance only has the two lists
        self.assertEqual(len(filtered_lists._by_name), 2)
        self.assertIn('To Do', filtered_lists._by_name)
        self.assertIn('Done (Closed)', filtered_lists._by_name)
        # Check that the _filtered flag is set in the new instance (implicitly tested by trello_lists_param usage)
        self.assertTrue(filtered_lists._filtered)

    def test_filter_list_not_found(self):
        filter_names = ['To Do', 'Non-Existent List', 'Another Missing']

        # Expect a ValueError to be raised
        with self.assertRaisesRegex(ValueError, "The following lists were not found on the board: 'Non-Existent List', 'Another Missing'"):
            self.trello_lists.filter_by_list_names(filter_names)

class TestTrelloChecklistItem(unittest.TestCase):
    """Tests for the TrelloChecklistItem get_html method."""

    def test_get_html_with_url(self):
        item = TrelloChecklistItem(
            id='c1', value='Do task', checked=False,
            url='http://example.com/task', url_title='Task Link',
            pos=11111
        )
        expected_html = '<a href=http://example.com/task>Task Link</a>'
        self.assertEqual(item.get_html(), expected_html)

    def test_get_html_without_url(self):
        item = TrelloChecklistItem(id='c1', value='Do task', checked=False, pos=11111)
        # Should return just the value
        self.assertEqual(item.get_html(), 'Do task')

class TestTrelloBoard(unittest.TestCase):
    """Tests for the TrelloBoard __post_init__ logic."""

    def test_simple_name_creation(self):
        mock_list = MagicMock()
        board = TrelloBoard(
            id='b1', json='{}', name='My Awesome Trello Board / V1.0',
            lists=[mock_list]
        )
        # The logic should replace spaces, slashes, and backslashes with hyphens, and make it lowercase
        self.assertEqual(board.simple_name, 'my-awesome-trello-board-v1.0')

    def test_simple_name_no_special_chars(self):
        mock_list = MagicMock()
        board = TrelloBoard(
            id='b2', json='{}', name='ProjectAlpha',
            lists=[mock_list]
        )
        self.assertEqual(board.simple_name, 'projectalpha')

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)