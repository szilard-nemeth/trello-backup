from typing import Dict, List, Any

from trello_backup.trello.api import TrelloApi
from trello_backup.trello.cache import WebpageTitleCache
from trello_backup.trello.model import TrelloList, TrelloChecklist, TrelloComment, TrelloChecklistItem, TrelloCard, \
    TrelloAttachment, TrelloBoard, TrelloLists, TrelloChecklists, TrelloCards


class TrelloOperations:
    def __init__(self):
        self._board_name_to_board_id: Dict[str, str] = {}
        self._board_id_to_board_json: Dict[str, Any] = {}
        # Initialize WebpageTitleCache so 'board.get_checklist_url_titles' can use it
        self.cache = WebpageTitleCache()
        self.cache.load()

    def get_board(self, name: str, download_comments: bool = False):
        board_id = self._get_board_id(name)
        board_json = self._get_board_json(board_id)

        # Parse JSON to objects
        trello_lists = TrelloLists(board_json)
        trello_checklists = TrelloChecklists(board_json)
        trello_cards = TrelloCards(board_json, trello_lists, trello_checklists, download_comments=download_comments)

        board = TrelloBoard(board_id, name, trello_lists.open)
        board.get_checklist_url_titles(self.cache)

        # Download attachments
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


class TrelloObjectParser:
    @staticmethod
    def parse_trello_lists(board_json):
        lists = board_json["lists"]

        parsed_lists = []
        for list in lists:
            trello_list = TrelloList(list["closed"], list["id"], list["name"], list["idBoard"])
            parsed_lists.append(trello_list)
        return parsed_lists

    @staticmethod
    def parse_trello_cards(board_json,
                           trello_lists: TrelloLists,
                           trello_checklists: TrelloChecklists,
                           download_comments: bool = False):
        cards_json = board_json["cards"]
        cards = []
        for idx, card in enumerate(cards_json):
            print("Processing card: {} / {}".format(idx + 1, len(cards_json)))
            trello_list = trello_lists.by_id[card["idList"]]
            label_names = [l["name"] for l in card["labels"]]
            checklist_ids = card["idChecklists"]
            checklists = [trello_checklists.by_id[cid] for cid in checklist_ids]

            comments = []
            if download_comments:
                comments: List[TrelloComment] = TrelloObjectParser.query_comments_for_card(card)

            attachments = []
            if "attachments" in card and len(card["attachments"]) > 0:
                for attachment_json in card["attachments"]:
                    #attachment_json = get_attachment_of_card(card["id"])
                    is_upload = attachment_json["isUpload"]
                    attachment_api_url = None
                    if is_upload:
                        attachment_api_url = TrelloObjectParser.reformat_attachment_url(card["id"], attachment_json["id"], attachment_json["fileName"])

                    trello_attachment = TrelloAttachment(attachment_json["id"],
                                                         attachment_json["date"],
                                                         attachment_json["name"],
                                                         attachment_json["url"],
                                                         attachment_api_url,
                                                         is_upload,
                                                         attachment_json["fileName"],
                                                         None)
                    attachments.append(trello_attachment)

            trello_card = TrelloCard(card["id"], card["name"], trello_list, card["desc"], attachments, checklists, label_names, card["closed"], comments, card["due"], [])
            cards.append(trello_card)
            trello_list.cards.append(trello_card)
        return cards

    @staticmethod
    def reformat_attachment_url(card_id, attachment_id, attachment_filename):
        # Convert URLs as Trello attachments cannot be downloaded from trello.com URL anymore..
        # See details here: https://community.developer.atlassian.com/t/update-authenticated-access-to-s3/43681
        # Example URL: https://api.trello.com/1/cards/{idCard}/attachments/{idAttachment}/download/{attachmentFileName}
        # Source: https://trello.com/1/cards/60d8951d65e3c9345794d20a/attachments/631332fc6b78cf0135be0a37/download/image.png
        # Target: https://api.trello.com/1/cards/60d8951d65e3c9345794d20a/attachments/631332fc6b78cf0135be0a37/download/image.png
        return "https://api.trello.com/1/cards/{c_id}/attachments/{a_id}/download/{a_fname}".format(c_id=card_id, a_id=attachment_id, a_fname=attachment_filename)

    @staticmethod
    def query_comments_for_card(card) -> List[TrelloComment]:
        actions = TrelloApi.get_actions_for_card(card["id"])
        comment_actions_json = list(filter(lambda a: a['type'] == "commentCard", actions))
        comments = []
        for action in comment_actions_json:
            member_creator = action['memberCreator']
            author = member_creator["username"]

            if 'data' not in action:
                # TODO warning log
                continue
            data = action['data']
            if 'text' not in data:
                # TODO warning log
                continue
            trello_comment = TrelloComment(action["id"], author, action["date"], data['text'])
            comments.append(trello_comment)
        return comments

    @staticmethod
    def parse_trello_checklists(board_json):
        checklists = board_json["checklists"]

        trello_checklists = []
        for checklist in checklists:
            checkitems_json = checklist["checkItems"]
            trello_checklist_items = []
            for checkitem in checkitems_json:
                trello_checklist_item = TrelloChecklistItem(checkitem["id"], checkitem["name"], checkitem["state"] == "complete")
                trello_checklist_items.append(trello_checklist_item)

            trello_checklist = TrelloChecklist(checklist["id"], checklist["name"], checklist["idBoard"], checklist["idCard"], trello_checklist_items)
            trello_checklists.append(trello_checklist)
        return trello_checklists
