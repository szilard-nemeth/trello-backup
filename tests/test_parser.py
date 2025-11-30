import unittest
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any

from trello_backup.trello.api import TrelloApi
from trello_backup.trello.model import TrelloList, TrelloChecklist, TrelloAttachment, TrelloComment
from trello_backup.trello.parser import TrelloObjectParser


# Mocking the TrelloLists and TrelloChecklists container classes for ease of lookup
class MockTrelloLists:
    def __init__(self, lists, is_filtered=False):
        self.by_id = {l.id: l for l in lists}
        self._filtered = is_filtered

class MockTrelloChecklists:
    def __init__(self, checklists):
        self.by_id = {c.id: c for c in checklists}


class TrelloObjectParserTest(unittest.TestCase):

    def setUp(self):
        pass

    # --- Test Data ---
    MOCK_BOARD_ID = "mock_board_id_1"

    MOCK_LISTS_JSON = [
        {"closed": False, "id": "list_id_1", "name": "To Do", "idBoard": MOCK_BOARD_ID},
        {"closed": True, "id": "list_id_2", "name": "Done", "idBoard": MOCK_BOARD_ID},
    ]

    MOCK_CHECKLISTS_JSON = [
        {
            "id": "checklist_id_1",
            "name": "Steps 1",
            "idBoard": MOCK_BOARD_ID,
            "idCard": "card_id_1",
            "checkItems": [
                {"id": "checkitem_id_1_1", "name": "Step 1", "state": "complete"},
                {"id": "checkitem_id_1_2", "name": "Step 2", "state": "incomplete"},
            ],
        },
        {
            "id": "checklist_id_2",
            "name": "Steps 2",
            "idBoard": MOCK_BOARD_ID,
            "idCard": "card_id_1",
            "checkItems": [
                {"id": "checkitem_id_2_1", "name": "Step 1_1", "state": "complete"},
                {"id": "checkitem_id_2_2", "name": "Step 1_2", "state": "incomplete"},
            ],
        }
    ]

    MOCK_CARDS_JSON = [
        {
            "id": "card_id_1",
            "name": "Feature X",
            "idList": "list_id_1",
            "desc": "Card description.",
            "closed": False,
            "due": None,
            "labels": [{"name": "P1"}, {"name": "Feature"}],
            "idChecklists": ["checklist_id_1", "checklist_id_2"],
            "attachments": [
                {
                    "id": "att_id_1",
                    "date": "2025-01-01T10:00:00.000Z",
                    "name": "report.pdf",
                    "url": "https://trello-url/att_1",
                    "isUpload": True,
                    "fileName": "report.pdf"
                }
            ],
        },
        {
            "id": "card_id_2",
            "name": "Bug Y",
            "idList": "list_id_2",
            "desc": "Another description.",
            "closed": True,
            "due": "2025-11-20T12:00:00.000Z",
            "labels": [],
            "idChecklists": [],
            "attachments": [],
        },
    ]

    MOCK_BOARD_JSON: Dict[str, Any] = {
        "lists": MOCK_LISTS_JSON,
        "cards": MOCK_CARDS_JSON,
        "checklists": MOCK_CHECKLISTS_JSON,
        "id": MOCK_BOARD_ID
    }


    def test_parse_trello_lists_success(self):
        """Tests successful parsing of multiple lists."""
        result = TrelloObjectParser.parse_trello_lists(self.MOCK_BOARD_JSON)

        self.assertEqual(len(result), 2)
        list_1: TrelloList = result[0]
        list_2: TrelloList = result[1]

        self.assertFalse(list_1.closed)
        self.assertEqual(list_1.id, "list_id_1")
        self.assertEqual(list_1.name, "To Do")
        self.assertEqual(list_1.board_id, TrelloObjectParserTest.MOCK_BOARD_ID)

        self.assertTrue(list_2.closed)
        self.assertEqual(list_2.id, "list_id_2")
        self.assertEqual(list_2.name, "Done")
        self.assertEqual(list_2.board_id, TrelloObjectParserTest.MOCK_BOARD_ID)


    def test_parse_trello_checklists_success(self):
        """Tests successful parsing of a checklist with items."""
        result = TrelloObjectParser.parse_trello_checklists(self.MOCK_BOARD_JSON)

        self.assertEqual(len(result), 2)
        cl_1 = result[0]
        cl_2 = result[1]
        self._assert_two_checklists(cl_1, cl_2)

    def _assert_two_checklists(self, cl_1, cl_2):
        self.assertEqual("checklist_id_1", cl_1.id)
        self.assertEqual("Steps 1", cl_1.name)
        self.assertEqual(TrelloObjectParserTest.MOCK_BOARD_ID, cl_1.board_id)
        self.assertEqual("card_id_1", cl_1.card_id)

        self.assertEqual(2, len(cl_1.items))
        self.assertEqual("checkitem_id_1_1", cl_1.items[0].id)
        self.assertEqual("Step 1", cl_1.items[0].value)
        self.assertTrue(cl_1.items[0].checked)

        self.assertEqual("checkitem_id_1_2", cl_1.items[1].id)
        self.assertEqual("Step 2", cl_1.items[1].value)
        self.assertFalse(cl_1.items[1].checked)

        self.assertEqual("checklist_id_2", cl_2.id)
        self.assertEqual("Steps 2", cl_2.name)
        self.assertEqual(TrelloObjectParserTest.MOCK_BOARD_ID, cl_2.board_id)
        self.assertEqual("card_id_1", cl_2.card_id)

        self.assertEqual(2, len(cl_2.items))
        self.assertEqual("checkitem_id_2_1", cl_2.items[0].id)
        self.assertEqual("Step 1_1", cl_2.items[0].value)
        self.assertTrue(cl_2.items[0].checked)

        self.assertEqual("checkitem_id_2_2", cl_2.items[1].id)
        self.assertEqual("Step 1_2", cl_2.items[1].value)
        self.assertFalse(cl_2.items[1].checked)

    def test_parse_trello_cards_no_comments_no_attachments(self):
        """Tests basic card parsing without comments or attachments."""
        # Setup mock lists and checklists containers
        mock_list_1 = MagicMock(spec=TrelloList, id="list_id_1", cards=[])
        mock_list_2 = MagicMock(spec=TrelloList, id="list_id_2", cards=[])
        mock_trello_lists = MockTrelloLists(lists=[mock_list_1, mock_list_2])

        mock_checklist_1 = MagicMock(spec=TrelloChecklist, id="checklist_id_1")
        mock_checklist_2 = MagicMock(spec=TrelloChecklist, id="checklist_id_2")
        mock_trello_checklists = MockTrelloChecklists(checklists=[mock_checklist_1, mock_checklist_2])

        # Overwrite the cards JSON to simplify the test case
        simple_cards_json = [
            {
                "id": "card_id_1",
                "name": "Simple Card",
                "idList": "list_id_1",
                "desc": "description",
                "closed": False,
                "due": None,
                "labels": [{"name": "Test"}],
                "idChecklists": [], # No checklists
                "attachments": [], # No attachments
            }
        ]

        board_json = {"cards": simple_cards_json}

        cards = TrelloObjectParser.parse_trello_cards(
            board_json,
            mock_trello_lists,
            mock_trello_checklists,
            download_comments=False
        )

        self.assertEqual(1, len(cards))
        self.assertEqual("card_id_1", cards[0].id)
        self.assertEqual("Simple Card", cards[0].name)
        self.assertFalse(cards[0].closed)
        self.assertEqual(mock_list_1, cards[0].list)
        self.assertEqual("description", cards[0].description)
        self.assertEqual([], cards[0].attachments)
        self.assertEqual([], cards[0].checklists)
        self.assertEqual([], cards[0].comments)
        self.assertEqual(["Test"], cards[0].labels)
        self.assertEqual("card_id_1", cards[0].id)
        self.assertIsNone(cards[0].due_date)

    def test_parse_trello_cards_with_attachments(self):
        """Tests card parsing including attachment logic."""
        # Setup mock lists and checklists containers
        mock_list_1 = MagicMock(spec=TrelloList, id="list_id_1", cards=[])
        mock_trello_lists = MockTrelloLists(lists=[mock_list_1])

        mock_checklist_1 = MagicMock(spec=TrelloChecklist, id="checklist_id_1")
        mock_checklist_2 = MagicMock(spec=TrelloChecklist, id="checklist_id_2")
        mock_trello_checklists = MockTrelloChecklists(checklists=[mock_checklist_1, mock_checklist_2])

        board_json = {"cards": self.MOCK_CARDS_JSON[:1]} # Only the first card with an attachment

        cards = TrelloObjectParser.parse_trello_cards(
            board_json,
            mock_trello_lists,
            mock_trello_checklists,
            download_comments=False
        )

        self._assert_card1_common(cards, mock_list_1)
        self.assertEqual([], cards[0].comments)

        self.assertEqual(1, len(cards[0].attachments))
        attachment: TrelloAttachment = cards[0].attachments[0]
        self.assertEqual("att_id_1", attachment.id)
        self.assertEqual("2025-01-01T10:00:00.000Z", attachment.date)
        self.assertEqual("report.pdf", attachment.name)
        self.assertEqual("report.pdf", attachment.file_name)
        self.assertEqual("https://trello-url/att_1", attachment.url)
        self.assertEqual("https://api.trello.com/1/cards/card_id_1/attachments/att_id_1/download/report.pdf", attachment.api_url)
        self.assertTrue(attachment.is_upload)

    def _assert_card1_common(self, cards: list[Any], mock_list_1: MagicMock):
        self.assertEqual(1, len(cards))
        self.assertEqual("card_id_1", cards[0].id)
        self.assertEqual("Feature X", cards[0].name)
        self.assertFalse(cards[0].closed)
        self.assertEqual(mock_list_1, cards[0].list)
        self.assertEqual("Card description.", cards[0].description)
        self.assertEqual(2, len(cards[0].checklists))
        self.assertEqual(["P1", "Feature"], cards[0].labels)
        self.assertEqual("card_id_1", cards[0].id)
        self.assertIsNone(cards[0].due_date)

    @patch.object(TrelloObjectParser, 'query_comments_for_card')
    def test_parse_trello_cards_with_comment_download(self, mock_query_comments):
        """Tests that comment downloading is triggered when requested."""
        # Setup mock lists and checklists containers
        mock_list_1 = MagicMock(spec=TrelloList, id="list_id_1", cards=[])
        mock_trello_lists = MockTrelloLists(lists=[mock_list_1])
        mock_checklist_1 = MagicMock(spec=TrelloChecklist, id="checklist_id_1")
        mock_checklist_2 = MagicMock(spec=TrelloChecklist, id="checklist_id_2")
        mock_trello_checklists = MockTrelloChecklists(checklists=[mock_checklist_1, mock_checklist_2])

        # Mock the result of query_comments_for_card
        mock_comment_1 = MagicMock(spec=TrelloComment)
        mock_comment_1.contents = "comment 1"
        mock_comment_2 = MagicMock(spec=TrelloComment)
        mock_comment_2.contents = "comment 2"
        mock_query_comments.return_value = [mock_comment_1, mock_comment_2]

        board_json = {"cards": self.MOCK_CARDS_JSON[:1]}

        cards = TrelloObjectParser.parse_trello_cards(
            board_json,
            mock_trello_lists,
            mock_trello_checklists,
            download_comments=True # Important flag
        )

        self._assert_card1_common(cards, mock_list_1)
        self.assertEqual(2, len(cards[0].comments))
        self.assertEqual("comment 1", cards[0].comments[0].contents)
        self.assertEqual("comment 2", cards[0].comments[1].contents)


    def test_parse_trello_cards_filtered_skip(self):
        """Tests that cards for non-present lists are skipped when TrelloLists is filtered."""
        # Setup TrelloLists as filtered, only containing list_id_2
        mock_list_2 = MagicMock(spec=TrelloList, id="list_id_2", cards=[])
        mock_trello_lists = MockTrelloLists(lists=[mock_list_2], is_filtered=True) # Important flag
        mock_trello_checklists = MockTrelloChecklists(checklists=[])

        board_json = {"cards": self.MOCK_CARDS_JSON} # Card 1 is for list_id_1, Card 2 is for list_id_2

        cards = TrelloObjectParser.parse_trello_cards(
            board_json,
            mock_trello_lists,
            mock_trello_checklists,
            download_comments=False
        )

        self.assertEqual(1, len(cards))
        self.assertEqual("card_id_2", cards[0].id)

    @patch.object(TrelloApi, 'get_actions_for_card')
    def test_query_comments_for_card_success(self, mock_get_actions):
        """Tests successful parsing of a comment action."""
        mock_actions_json = [
            {"id": "action_id_1", "type": "commentCard", "date": "2025-01-02T10:00:00.000Z",
             "memberCreator": {"username": "user1"}, "data": {"text": "A test comment 1."}},
            {"id": "action_id_2", "type": "updateCard", "date": "...",
             "memberCreator": {"username": "user2"}, "data": {"text": "Not a comment."}},
            {"id": "action_id_3", "type": "commentCard", "date": "2025-02-02T10:00:00.000Z",
             "memberCreator": {"username": "user3"}, "data": {"text": "A test comment 2."}},
        ]
        mock_get_actions.return_value = mock_actions_json

        mock_card_json = {"id": "card_id_1", "name": "Test Card"}
        comments = TrelloObjectParser.query_comments_for_card(mock_card_json)

        self.assertEqual(2, len(comments))
        self.assertEqual("action_id_1", comments[0].id)
        self.assertEqual("user1", comments[0].author)
        self.assertEqual("2025-01-02T10:00:00.000Z", comments[0].date)
        self.assertEqual("A test comment 1.", comments[0].contents)

        self.assertEqual("action_id_3", comments[1].id)
        self.assertEqual("user3", comments[1].author)
        self.assertEqual("2025-02-02T10:00:00.000Z", comments[1].date)
        self.assertEqual("A test comment 2.", comments[1].contents)


    @patch.object(TrelloApi, 'get_actions_for_card')
    def test_query_comments_for_card_missing_data_keys(self, mock_get_actions):
        """Tests handling of comment actions missing 'data' or 'text' keys."""
        mock_actions_json = [
            {"id": "a_id_1", "type": "commentCard", "date": "...", "memberCreator": {"username": "u1"}}, # Missing 'data'
            {"id": "a_id_2", "type": "commentCard", "date": "...", "memberCreator": {"username": "u2"}, "data": {}}, # Missing 'text'
            {"id": "a_id_3", "type": "commentCard", "date": "2025-01-02T10:00:00.000Z", "memberCreator": {"username": "user3"}, "data": {"text": "Valid."}},
        ]
        mock_get_actions.return_value = mock_actions_json

        mock_card_json = {"id": "card_id_1", "name": "Test Card"}

        comments = TrelloObjectParser.query_comments_for_card(mock_card_json)

        self.assertEqual(1, len(comments))
        self.assertEqual("a_id_3", comments[0].id)
        self.assertEqual("user3", comments[0].author)
        self.assertEqual("2025-01-02T10:00:00.000Z", comments[0].date)
        self.assertEqual("Valid.", comments[0].contents)