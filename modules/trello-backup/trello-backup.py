import json
import pickle
from dataclasses import dataclass, field
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from pythoncommons.file_utils import FileUtils
from pythoncommons.url_utils import UrlUtils

import config



ORGANIZATION_ID = "60b31169ff7e174519a40577"
INDENT = "&nbsp;&nbsp;&nbsp;&nbsp;"
BS4_HTML_PARSER = "html.parser"


@dataclass
class TrelloCardHtmlGeneratorConfig:
    include_labels: bool
    include_due_date: bool
    include_checklists: bool
    include_activity: bool
    include_comments: bool

    @property
    def download_comments(self):
        return self.include_comments and self.include_activity


TRELLO_CARD_GENERATOR_MINIMAL_CONFIG = TrelloCardHtmlGeneratorConfig(include_labels=False,
                                                                     include_due_date=False,
                                                                     include_checklists=True,
                                                                     include_activity=False,
                                                                     include_comments=False)
TRELLO_CARD_GENERATOR_FULL_CONFIG = TrelloCardHtmlGeneratorConfig(include_labels=True,
                                                                     include_due_date=True,
                                                                     include_checklists=True,
                                                                     include_activity=True,
                                                                     include_comments=True)

TRELLO_CARD_GENERATOR_BASIC_CONFIG = TrelloCardHtmlGeneratorConfig(include_labels=True,
                                                                     include_due_date=True,
                                                                     include_checklists=True,
                                                                     include_activity=False,
                                                                     include_comments=False)




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
class TrelloActivity:
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
    due_date: str
    activities: List[TrelloActivity]


@dataclass
class TrelloBoard:
    id: str
    name: str
    lists: List[TrelloList]


class HtmlParser:
    js_renderer = None

    @staticmethod
    def create_bs(html) -> BeautifulSoup:
        return BeautifulSoup(html, features=BS4_HTML_PARSER)

    @staticmethod
    def create_bs_from_url(url, headers=None):
        resp = requests.get(url, headers=headers)
        soup = HtmlParser.create_bs(resp.text)
        return soup

    @classmethod
    def get_title_from_url(cls, url):
        print("Getting webpage title for URL: {}".format(url))
        soup = HtmlParser.create_bs_from_url(url)
        title = soup.title.string
        print("Found webpage title: {}".format(title))
        return str(title)

    @classmethod
    def get_title_from_url_with_js(cls, url):
        soup = HtmlParser.js_renderer.render_with_javascript(url, force_use_requests=True)
        title = soup.title.string
        return title



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
                       trello_checklists_by_id: Dict[str, TrelloChecklist],
                       html_gen_config: TrelloCardHtmlGeneratorConfig):
    cards_json = board_details_json["cards"]
    cards = []
    for idx, card in enumerate(cards_json):
        print("Processing card: {} / {}".format(idx + 1, len(cards_json)))
        trello_list = trello_lists_by_id[card["idList"]]
        label_names = [l["name"] for l in card["labels"]]
        checklist_ids = card["idChecklists"]
        checklists = [trello_checklists_by_id[cid] for cid in checklist_ids]

        comments = []
        if html_gen_config.download_comments:
            comments: List[TrelloComment] = query_comments_for_card(card)
        trello_card = TrelloCard(card["id"], card["name"], trello_list, card["desc"], checklists, label_names, card["closed"], comments, card["due"], [])
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


class TrelloBoardHtmlGenerator:
    def __init__(self, board, config, webpage_title_cache):
        self._webpage_title_cache = webpage_title_cache
        self.board = board
        self.config: TrelloCardHtmlGeneratorConfig = config
        self.default_style = """
            <style>
                .outer {
                    width: 200px;
                    margin: 0 auto;
                    background-color: yellow;
                }

                .inner {
                    margin-left: 50px;
                }
    	    </style>
            """

    @staticmethod
    def format_plain_text_description(card):
        # TODO is this required?
        # print("Original description: {}".format(card.description))
        if not card.description:
            return ""
        desc = card.description
        # desc = indent + desc.replace(/<br\s*\/?>/gi, "<br>" + indent)
        # print("Modified description: {}".format(desc))
        return f"<div class=\"inner\">{desc}</div><br>"

    @staticmethod
    def format_comment(comment: TrelloComment):
        return f"{INDENT * 2} {comment.author} : {comment.contents} ({comment.date})"

    @staticmethod
    def format_comments(card):
        comments_str = ""
        for comment in card.comments:
            comments_str += f"{TrelloBoardHtmlGenerator.format_comment(comment)}<br>"
        return comments_str

    @staticmethod
    def format_activity(activity):
        return f"{INDENT * 2} {activity.author} : {activity.contents} ({activity.date})"

    @staticmethod
    def format_activities(card):
        act_str = ""
        for activity in card.activities:
            act_str += f"{TrelloBoardHtmlGenerator.format_activity(activity)}<br>"
        return act_str

    def format_checklist(self, checklist: TrelloChecklist):
        items_str = ""
        for item in checklist.items:
            item_value = item.name
            try:
                url = UrlUtils.extract_from_str(item_value)
                if url:
                    if url not in self._webpage_title_cache:
                        url_title = HtmlParser.get_title_from_url(url)
                        if url_title:
                            self._webpage_title_cache[url] = url_title
                    else:
                        url_title = self._webpage_title_cache[url]
                    if not url_title:
                        url_title = url
                    item_value = f"<a href={url}>{url_title}</a>"
            except:
                pass
            item_str = "[x] " if item.checked else "[] "
            item_str += item_value + "<br>"
            items_str += f"{INDENT * 3}{item_str}"
        return f"<p class=\"checklist\">{items_str}</p>"

    def format_checklists(self, card):
        checklist_str = ""
        for checklist in card.checklists:
            checklist_str += f"<b>{INDENT * 2}{checklist.name}</b>{self.format_checklist(checklist)}"
        return f"<p class=\"checklists\">{checklist_str}</p>"

    def _render_card(self, list, card):
        html = "<hr/><div class =\"card\">"
        html += f"<h2>CARD: {card.name}</h2>"
        html += f"{INDENT}<h3>LIST: </h3><p class=\"list\">{INDENT * 2}{list.name}</p>"

        if card.description:
            html += self.format_plain_text_description(card)
        if self.config.include_labels:
            html += f"{INDENT}<h3>LABELS: </h3><p class=\"labels\">{INDENT * 2}{card.labels}</p>"
        if self.config.include_due_date:
            due_date = card.due_date if card.due_date else "N/A"
            html += f"{INDENT}<h3>DUE DATE: </h3><p class=\"dueDate\">{INDENT * 2}{due_date}</p>"
        if self.config.include_comments:
            html += f"{INDENT}<h3>COMMENTS: </h3><p class=\"comments\">{self.format_comments(card)}</p>"
        if self.config.include_activity:
            html += f"{INDENT}<h3>ACTIVITY HISTORY: </h3><p class=\"activity\">{self.format_activities(card)}</p>"
        if self.config.include_checklists:
            if card.checklists:
                html += f"{INDENT}<h3>CHECKLISTS: </h3><br>{self.format_checklists(card)}"
        html += "</div>"
        return html

    def render(self):
        html = self.default_style
        for trello_list in self.board.lists:
            html += f"<h1>LIST: {trello_list.name} ({len(trello_list.cards)} cards)</h1><br><br>"
            for card in trello_list.cards:
                html += self._render_card(trello_list, card)
        return html


def load_webpage_title_cache() -> Dict[str, str]:
    with open('webpage_title_cache.pickle', 'rb') as handle:
        try:
            return pickle.load(handle)
        except:
            return {}


def save_webpage_title_cache(data):
    with open('webpage_title_cache.pickle', 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)


if __name__ == '__main__':
    validate_config()
    html_gen_config = TRELLO_CARD_GENERATOR_BASIC_CONFIG

    # board_resp = get_board()
    # print(json.dumps(json.loads(board_resp.text), sort_keys=True, indent=4, separators=(",", ": ")))
    boards = list_boards()
    print(boards)

    #board_id = boards['PERSONAL: Weekly Plan']
    board_name = 'LEARN / RESEARCH'
    board_id = boards[board_name]

    board_details_json = get_board_details(board_id)

    # 1. parse lists
    trello_lists_all = parse_trello_lists(board_details_json)
    trello_lists_by_id = {l.id: l for l in trello_lists_all}

    # 2. Parse checklists
    trello_checklists = parse_trello_checklists(board_details_json)
    trello_checklists_by_id = {c.id: c for c in trello_checklists}

    trello_cards_all = parse_trello_cards(board_details_json, trello_lists_by_id, trello_checklists_by_id, html_gen_config)
    trello_cards_open = list(filter(lambda c: not c.closed, trello_cards_all))

    # Filter open trello lists
    trello_lists_open = list(filter(lambda tl: not tl.closed, trello_lists_all))
    print(trello_lists_open)

    board = TrelloBoard(board_id, board_name, trello_lists_open)

    webpage_title_cache = load_webpage_title_cache()
    html_gen = TrelloBoardHtmlGenerator(board, html_gen_config, webpage_title_cache)
    html = html_gen.render()
    save_webpage_title_cache(webpage_title_cache)
    FileUtils.write_to_file("/tmp/board-learn-research.html", html)

    # TODO add file cache that stores in the following hierarchy:
    #  <maindir>/boards/<board>/cards/<card>/actions/<action_id>.json

