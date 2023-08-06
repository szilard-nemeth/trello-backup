import json
from dataclasses import dataclass, field
from typing import List, Dict

import requests
import config



ORGANIZATION_ID = "60b31169ff7e174519a40577"


class QueryUtils:
    common_query = None
    headers = {
        "Accept": "application/json"
    }

@dataclass
class TrelloComment:
    id: str
    author: str
    date: str
    contents: str


@dataclass
class TrelloChecklistItem:
    id: str
    name: str
    checked: bool


@dataclass
class TrelloChecklist:
    id: str
    name: str
    board_id: str
    card_id: str
    items: List[TrelloChecklistItem]


@dataclass
class TrelloList:
    closed: bool
    id: str
    name: str
    board_id: str
    cards: List['TrelloCard'] = field(default_factory=list)


@dataclass
class TrelloCard:
    id: str
    name: str
    list: TrelloList
    description: str
    checklists: List[TrelloChecklist]
    labels: List[str]
    closed: bool
    comments: List[TrelloComment]


def get_board_details(board_id):
    params = {
        "fields": "all",
        "actions": "all",
        "action_fields": "all",
        "actions_limit": 1000,
        "cards": "all",
        "card_fields": "all",
        "card_attachments": "true",
        "labels": "all",
        "lists": "all",
        "list_fields": "all",
        "members": "all",
        "member_fields": "all",
        "checklists": "all",
        "checklist_fields": "all",
        "organization": "false",
    }

    url = "https://api.trello.com/1/boards/{board_id}/".format(board_id=board_id)
    query = QueryUtils.common_query
    query.update(params)
    response = requests.request(
        "GET",
        url,
        headers=QueryUtils.headers,
        params=query
    )
    response.raise_for_status()

    parsed_json = json.loads(response.text)

    return parsed_json



def get_board_json():
    url = "https://trello.com/b/9GZZWy03/personal-weekly-plan.json"

    response = requests.request(
        "GET",
        url,
        headers=QueryUtils.headers,
        params=QueryUtils.common_query
    )
    #code = response.status_code
    response.raise_for_status()
    return response


def get_lists_of_board():
    url = "https://api.trello.com/1/boards/{id}/lists"

    headers = {
        "Accept": "application/json"
    }

    query = {
        'key': 'APIKey',
        'token': 'APIToken'
    }

    response = requests.request(
        "GET",
        url,
        headers=headers,
        params=query
    )

    print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))


def create_card():
    url = "https://api.trello.com/1/cards"

    headers = {
        "Accept": "application/json"
    }

    query = QueryUtils.common_query.update({'idList': '5abbe4b7ddc1b351ef961414'})
    response = requests.request(
        "POST",
        url,
        headers=headers,
        params=query
    )

    print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))


def list_boards():
    url = "https://api.trello.com/1/organizations/{org_id}/boards".format(org_id=ORGANIZATION_ID)
    response = requests.request(
        "GET",
        url,
        headers=QueryUtils.headers,
        params=QueryUtils.common_query
    )

    parsed_json = json.loads(response.text)

    result_dict = {}
    for board in parsed_json:
        b_name = board['name']
        b_id = board['id']
        result_dict[b_name] = b_id

    # TODO debug log
    #print(json.dumps(parsed_json, sort_keys=True, indent=4, separators=(",", ": ")))
    return result_dict


def parse_trello_lists(board_details_json):
    lists = board_details_json["lists"]

    parsed_lists = []
    for list in lists:
        trello_list = TrelloList(list["closed"], list["id"], list["name"], list["idBoard"])
        parsed_lists.append(trello_list)
    return parsed_lists


def parse_trello_cards(board_details_json,
                       trello_lists_by_id: Dict[str, TrelloList],
                       trello_checklists_by_id: Dict[str, TrelloChecklist]):
    cards_json = board_details_json["cards"]
    cards = []
    for idx, card in enumerate(cards_json):
        print("Processing card: {} / {}".format(idx + 1, len(cards_json)))
        trello_list = trello_lists_by_id[card["idList"]]
        label_names = [l["name"] for l in card["labels"]]
        checklist_ids = card["idChecklists"]
        checklists = [trello_checklists_by_id[cid] for cid in checklist_ids]
        comments: List[TrelloComment] = query_comments_for_card(card)
        trello_card = TrelloCard(card["id"], card["name"], trello_list, card["desc"], checklists, label_names, card["closed"], comments)
        cards.append(trello_card)
        trello_list.cards.append(trello_card)
    return cards


def query_comments_for_card(card) -> List[TrelloComment]:
    actions = get_actions_for_card(card["id"])
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


def get_actions_for_card(card_id: str):
    url = "https://api.trello.com/1/cards/{id}/actions".format(id=card_id)

    response = requests.request(
        "GET",
        url,
        headers=QueryUtils.headers,
        params=QueryUtils.common_query
    )

    #print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
    parsed_json = json.loads(response.text)
    return parsed_json


def parse_trello_checklists(board_details_json):
    checklists = board_details_json["checklists"]

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


def validate_config():
    if not config.token:
        raise ValueError("token not found!")
    if not config.api_key:
        raise ValueError("api key not found!")

    QueryUtils.common_query = {
        'key': config.api_key,
        'token': config.token
    }


def generate_html_for_board(trello_lists):
    HtmlGenerator


if __name__ == '__main__':
    validate_config()

    # board_resp = get_board()
    # print(json.dumps(json.loads(board_resp.text), sort_keys=True, indent=4, separators=(",", ": ")))
    boards = list_boards()
    print(boards)

    #board_id = boards['PERSONAL: Weekly Plan']
    board_id = boards['LEARN / RESEARCH']

    board_details_json = get_board_details(board_id)

    # 1. parse lists
    trello_lists_all = parse_trello_lists(board_details_json)
    trello_lists_by_id = {l.id: l for l in trello_lists_all}

    # 2. Parse checklists
    trello_checklists = parse_trello_checklists(board_details_json)
    trello_checklists_by_id = {c.id: c for c in trello_checklists}

    trello_cards_all = parse_trello_cards(board_details_json, trello_lists_by_id, trello_checklists_by_id)
    trello_cards_open = list(filter(lambda c: not c.closed, trello_cards_all))

    # Filter open trello lists
    trello_lists_open = list(filter(lambda tl: not tl.closed, trello_lists_all))
    print(trello_lists_open)

    # TODO add file cache that stores in the following hierarchy:
    #  <maindir>/boards/<board>/cards/<card>/actions/<action_id>.json

