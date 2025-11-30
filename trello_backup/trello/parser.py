from typing import List

from trello_backup.display.console import CliLogger
from trello_backup.trello.api import TrelloApi
from trello_backup.trello.model import TrelloList, TrelloLists, TrelloChecklists, TrelloComment, TrelloAttachment, \
    TrelloCard, TrelloChecklistItem, TrelloChecklist

import logging
LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)

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
            # TODO Add progress bar for cards
            CLI_LOG.info("Processing card: {} / {}".format(idx + 1, len(cards_json)))
            comments = []
            # TODO ASAP refactor: this does not belong here, Decouple fetching API from parser logic - Here we fetch the comments
            if download_comments:
                comments: List[TrelloComment] = TrelloObjectParser.query_comments_for_card(card)

            attachments = []
            if "attachments" in card and len(card["attachments"]) > 0:
                for attachment_json in card["attachments"]:
                    is_upload = attachment_json["isUpload"]
                    attachment_api_url = None
                    if is_upload:
                        attachment_api_url = TrelloApi.reformat_attachment_url(card["id"], attachment_json["id"], attachment_json["fileName"])

                    trello_attachment = TrelloAttachment(attachment_json["id"],
                                                         attachment_json["date"],
                                                         attachment_json["name"],
                                                         attachment_json["url"],
                                                         attachment_api_url,
                                                         is_upload,
                                                         attachment_json["fileName"],
                                                         None)
                    attachments.append(trello_attachment)

            if trello_lists._filtered and card["idList"] not in trello_lists.by_id:
                # Skip this card.
                # If TrelloLists are filtered (does not contain all the lists), we allow the card to be not present for the lists.
                continue
            trello_list = trello_lists.by_id[card["idList"]]
            label_names = [l["name"] for l in card["labels"]]
            checklist_ids = card["idChecklists"]
            checklists = [trello_checklists.by_id[cid] for cid in checklist_ids]
            trello_card = TrelloCard(card["id"],
                                     card["name"],
                                     trello_list,
                                     card["desc"],
                                     attachments,
                                     checklists,
                                     label_names,
                                     card["closed"],
                                     comments,
                                     card["due"],
                                     [])
            cards.append(trello_card)
            trello_list.cards.append(trello_card)
        return cards

    @staticmethod
    def query_comments_for_card(card) -> List[TrelloComment]:
        actions = TrelloApi.get_actions_for_card(card["id"])
        comment_actions_json = list(filter(lambda a: a['type'] == "commentCard", actions))
        comments = []
        for action in comment_actions_json:
            member_creator = action['memberCreator']
            author = member_creator["username"]

            if 'data' not in action:
                LOG.warning("Failed to parse comment for card: %s, No 'data' key found in action. Details: %s", card["name"], action)
                continue
            data = action['data']
            if 'text' not in data:
                LOG.warning("Failed to parse comment for card: %s, No 'text' key found in data. Details: %s", card["name"], data)
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

            # TODO ASAP refactor: Add checklist object to card object
            trello_checklist = TrelloChecklist(checklist["id"], checklist["name"], checklist["idBoard"], checklist["idCard"], trello_checklist_items)
            trello_checklists.append(trello_checklist)
        return trello_checklists
