import atexit
import json
import os
import pickle
import traceback
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from typing import List, Dict, Tuple

import requests
from bs4 import BeautifulSoup
from pythoncommons.file_utils import FileUtils, FindResultType, CsvFileUtils
from pythoncommons.project_utils import SimpleProjectUtils
from pythoncommons.result_printer import TableRenderingConfig, ResultPrinter, TabulateTableFormat
from pythoncommons.url_utils import UrlUtils
from output import MarkdownFormatter
import config



ORGANIZATION_ID = "60b31169ff7e174519a40577"
INDENT = "&nbsp;&nbsp;&nbsp;&nbsp;"
BS4_HTML_PARSER = "html.parser"
MD_FORMATTER = MarkdownFormatter()
OUTPUT_DIR = "/Users/snemeth/trello-backup-output"  # TODO Should use pythoncommons to determine output dir as yarndevtools does
OUTPUT_DIR_ATTACHMENTS = os.path.join(OUTPUT_DIR, "attachments")
HTTP_SERVER_PORT = 8000
HTTP_SERVER_INSTANCE = None


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


class CardFilter(Flag):
    NONE = 0
    OPEN = auto()  # TODO Apply this card filter
    WITH_CHECKLIST = auto()
    WITH_DESCRIPTION = auto()
    WITH_ATTACHMENT = auto()

    @classmethod
    def ALL(cls):
        retval = cls.NONE
        for member in cls.__members__.values():
            retval |= member
        return retval



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
REPO_ROOT_DIRNAME = "trello-backup"
TRELLO_BACKUP_MODULE_NAME = "trello_backup"
CARD_FILTER_ALL = CardFilter.ALL()
CARD_FILTER_DESC_AND_CHECKLIST = CardFilter.WITH_DESCRIPTION | CardFilter.WITH_CHECKLIST
CARD_FILTER_DESC_AND_ATTACHMENT = CardFilter.WITH_DESCRIPTION | CardFilter.WITH_ATTACHMENT
CARD_FILTER_CHECKLIST_AND_ATTACHMENT = CardFilter.WITH_CHECKLIST | CardFilter.WITH_ATTACHMENT
CARD_FILTER_ONLY_DESC = CardFilter.WITH_DESCRIPTION

ACTIVE_CARD_FILTERS = CARD_FILTER_ALL

class LocalDirsFiles:
    REPO_ROOT_DIR = FileUtils.find_repo_root_dir(__file__, REPO_ROOT_DIRNAME)
    TRELLO_BACKUP_DIR = SimpleProjectUtils.get_project_dir(
        basedir=REPO_ROOT_DIR,
        parent_dir="trello-backup",
        dir_to_find=TRELLO_BACKUP_MODULE_NAME,
        find_result_type=FindResultType.DIRS,
        exclude_dirs=[],
    )
    WEBPAGE_TITLE_CACHE_FILE = FileUtils.join_path(TRELLO_BACKUP_DIR, 'webpage_title_cache.pickle')


class TrelloUtils:
    auth_query_params = None
    authorization_headers = None
    headers_accept_json = {
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
    url: str = None
    url_title: str = None

    def get_html(self):
        if self.url:
            return f"<a href={self.url}>{self.url_title}</a>"
        return self.name


@dataclass
class TrelloChecklist:
    id: str
    name: str
    board_id: str
    card_id: str
    items: List[TrelloChecklistItem]

    def get_url_titles(self):
        import re
        for item in self.items:
            try:
                url = UrlUtils.extract_from_str(item.name)
            except:
                url = None
            if url:
                url_title = None
                if url not in webpage_title_cache:
                    # Fetch title of URL
                    try:
                        url_title = HtmlParser.get_title_from_url(url)
                        url_title = re.sub(r'[\n\t\r]+', ' ', url_title)
                    except Exception:
                        traceback.print_exc()
                        print("Failed to get title for URL: {}".format(url))
                    if url_title:
                        webpage_title_cache[url] = url_title
                else:
                    # Read from cache
                    old_url_title = webpage_title_cache[url]
                    new_url_title = re.sub(r'[\n\t\r]+', ' ', old_url_title)
                    if old_url_title != new_url_title:
                        webpage_title_cache[url] = new_url_title
                    url_title = new_url_title

                if not url_title:
                    url_title = url
                item.url_title = url_title
                item.url = url



@dataclass
class TrelloList:
    closed: bool
    id: str
    name: str
    board_id: str
    cards: List['TrelloCard'] = field(default_factory=list)


@dataclass
class TrelloAttachment:
    id: str
    date: str
    name: str
    url: str
    api_url: str
    is_upload: bool
    file_name: str
    downloaded_file_path: str


@dataclass
class TrelloCard:
    id: str
    name: str
    list: TrelloList
    description: str
    attachments: List[TrelloAttachment]
    checklists: List[TrelloChecklist]
    labels: List[str]
    closed: bool
    comments: List[TrelloComment]
    due_date: str
    activities: List[TrelloActivity]

    @property
    def has_description(self):
        return len(self.description) > 0

    @property
    def has_checklist(self):
        return len(self.checklists) > 0

    @property
    def has_attachments(self):
        return len(self.attachments) > 0

    def get_checklist_url_titles(self):
        for cl in self.checklists:
            cl.get_url_titles()

    def get_extracted_data(self, card_filter_flags: CardFilter):
        # Sanity check
        # has_checklists = self.has_checklist
        # has_attachments = self.has_attachments
        # has_description = self.has_description
        # if has_checklists and CardFilter.WITH_CHECKLIST not in card_filter_flags:
        #     raise ValueError("Card has checklists but card filters are not enabling checklists! Current filter: {}".format(card_filter_flags))
        # if has_description and CardFilter.WITH_DESCRIPTION not in card_filter_flags:
        #     raise ValueError("Card has description but card filters are not enabling description! Current filter: {}".format(card_filter_flags))
        # if has_attachments and CardFilter.WITH_ATTACHMENT not in card_filter_flags:
        #     raise ValueError("Card has attachments but card filters are not enabling attachments! Current filter: {}".format(card_filter_flags))

        # 1. Always add description to each row
        plain_text_description = MD_FORMATTER.to_plain_text(self.description)
        result = []
        if len(card_filter_flags) == 1 and CardFilter.WITH_DESCRIPTION in card_filter_flags:
            result.append(ExtractedCardData(plain_text_description, "", "", "", "", "", ""))
            return result

        # 2. Add attachments to separate row from checklist items
        if CardFilter.WITH_ATTACHMENT in card_filter_flags:
            for attachment in self.attachments:
                attachment_file_path = "" if not attachment.downloaded_file_path else attachment.downloaded_file_path

                local_server_path = ""
                if attachment.downloaded_file_path:
                    local_server_path = "http://localhost:{}/{}".format(HTTP_SERVER_PORT, attachment.downloaded_file_path.split("/")[-1])
                result.append(ExtractedCardData(plain_text_description, attachment.name, attachment.url, attachment_file_path, local_server_path, "", "", ""))

        # 3. Add checklist items to separate row from attachments
        if CardFilter.WITH_CHECKLIST in card_filter_flags:
            for cl in self.checklists:
                for item in cl.items:
                    cl_item_name = ""
                    cl_item_url_title = ""
                    cl_item_url = ""
                    if item.url:
                        cl_item_url_title = item.url_title
                        cl_item_url = item.url
                    else:
                        cl_item_name = item.name
                    result.append(ExtractedCardData(plain_text_description, "", "", "", "", cl_item_name, cl_item_url_title, cl_item_url))

        # If no append happened, append default ExtractedCardData
        if not result and CardFilter.WITH_DESCRIPTION in card_filter_flags:
            result.append(ExtractedCardData(plain_text_description, "", "", "", "", "", "", ""))
        return result

    def get_labels_as_str(self):
        return ",".join(self.labels)


@dataclass
class TrelloBoard:
    id: str
    name: str
    lists: List[TrelloList]

    def __post_init__(self):
        import re
        self.simple_name = re.sub("[ /\ ]+", "-", self.name).lower()

    def get_checklist_url_titles(self):
        for list in self.lists:
            for card in list.cards:
                card.get_checklist_url_titles()


@dataclass
class ExtractedCardData:
    description: str
    attachment_name: str
    attachment_url: str
    attachment_file_path: str
    local_server_path: str
    cl_item_name: str
    cl_item_url_title: str
    cl_item_url: str


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
    query = dict(TrelloUtils.auth_query_params)
    query.update(params)
    response = requests.request(
        "GET",
        url,
        headers=TrelloUtils.headers_accept_json,
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
        headers=TrelloUtils.headers_accept_json,
        params=TrelloUtils.auth_query_params
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
        'key': config.api_key,
        'token': config.token,
    }

    response = requests.request(
        "GET",
        url,
        headers=headers,
        params=query
    )

    print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))


def get_attachment_of_card(card_id: str):
    url = "https://api.trello.com/1/cards/{id}/actions".format(id=card_id)

    headers = {
        "Accept": "application/json"
    }

    query = {
        'key': config.api_key,
        'token': config.token,
    }

    response = requests.request(
        "GET",
        url,
        headers=headers,
        params=query
    )

    # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
    parsed_json = json.loads(response.text)
    return parsed_json


def create_card():
    url = "https://api.trello.com/1/cards"

    headers = {
        "Accept": "application/json"
    }

    query = TrelloUtils.auth_query_params.update({'idList': '5abbe4b7ddc1b351ef961414'})
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
        headers=TrelloUtils.headers_accept_json,
        params=TrelloUtils.auth_query_params
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

        attachments = []
        if "attachments" in card and len(card["attachments"]) > 0:
            for attachment_json in card["attachments"]:
                #attachment_json = get_attachment_of_card(card["id"])
                is_upload = attachment_json["isUpload"]
                attachment_api_url = None
                if is_upload:
                    attachment_api_url = reformat_attachment_url(card["id"], attachment_json["id"], attachment_json["fileName"])

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


def reformat_attachment_url(card_id, attachment_id, attachment_filename):
    # Convert URLs as Trello attachments cannot be downloaded from trello.com URL anymore..
    # See details here: https://community.developer.atlassian.com/t/update-authenticated-access-to-s3/43681
    # Example URL: https://api.trello.com/1/cards/{idCard}/attachments/{idAttachment}/download/{attachmentFileName}
    # Source: https://trello.com/1/cards/60d8951d65e3c9345794d20a/attachments/631332fc6b78cf0135be0a37/download/image.png
    # Target: https://api.trello.com/1/cards/60d8951d65e3c9345794d20a/attachments/631332fc6b78cf0135be0a37/download/image.png
    return "https://api.trello.com/1/cards/{c_id}/attachments/{a_id}/download/{a_fname}".format(c_id=card_id, a_id=attachment_id, a_fname=attachment_filename)


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
        headers=TrelloUtils.headers_accept_json,
        params=TrelloUtils.auth_query_params
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

    TrelloUtils.auth_query_params = {
        'key': config.api_key,
        'token': config.token
    }
    TrelloUtils.authorization_headers = {
        "Authorization": "OAuth oauth_consumer_key=\"{}\", oauth_token=\"{}\"".format(config.api_key, config.token)
    }


class TrelloBoardHtmlTableHeader(Enum):
    BOARD = "Board"
    LIST = "List"
    CARD = "Card"
    LABELS = "Labels"
    DUE_DATE = "Due date"
    DESCRIPTION = "Description"
    ATTACHMENT_NAME = "Attachment name"
    ATTACHMENT_URL = "Attachment URL"
    ATTACHMENT_LOCAL_URL = "Attachment Local URL"
    ATTACHMENT_FILE__PATH = "Attachment File path"
    CHECKLIST_ITEM_NAME = "Checklist item Name"
    CHECKLIST_ITEM_URL_TITLE = "Checklist item URL Title"
    CHECKLIST_ITEM_URL = "Checklist item URL"


class TrelloBoardHtmlTableGenerator:
    DEFAULT_TABLE_FORMATS = [TabulateTableFormat.HTML]

    def __init__(self, board):
        self.board = board
        self.tables = {}

    def render(self, rows, header):
        render_conf = TableRenderingConfig(
            row_callback=lambda row: row,
            print_result=False,
            max_width=200,
            max_width_separator=os.sep,
            tabulate_formats=TrelloBoardHtmlTableGenerator.DEFAULT_TABLE_FORMATS,
        )
        gen_tables = ResultPrinter.print_tables(
            data=rows,
            header=header,
            render_conf=render_conf,
        )

        self.tables: Dict[TabulateTableFormat, str] = gen_tables

    def write_file(self, file):
        for fmt, table in self.tables.items():
            FileUtils.save_to_file(file, table)
            print(f"Generated HTML table to file: {file}")


class TrelloBoardHtmlFileGenerator:
    def __init__(self, board, config):
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
            comments_str += f"{TrelloBoardHtmlFileGenerator.format_comment(comment)}<br>"
        return comments_str

    @staticmethod
    def format_activity(activity):
        return f"{INDENT * 2} {activity.author} : {activity.contents} ({activity.date})"

    @staticmethod
    def format_activities(card):
        act_str = ""
        for activity in card.activities:
            act_str += f"{TrelloBoardHtmlFileGenerator.format_activity(activity)}<br>"
        return act_str

    def format_checklist(self, checklist: TrelloChecklist):
        items_str = ""
        for item in checklist.items:
            item_str = "[x] " if item.checked else "[] "
            item_str += item.get_html() + "<br>"
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
        self.html = html

    def write_to_file(self, file):
        FileUtils.write_to_file(file, self.html)
        print("Generated HTML file output to: " + file)


class TrelloBoardRichTableGenerator:
    def __init__(self, board):
        self.board = board

    def render(self, rows, print_console=True):
        # TODO implement console mode --> Just print this and do not log anything to console other than the table
        # TODO add progressbar while loading emails
        from rich.console import Console
        from rich.table import Table
        table = Table(title=f"TRELLO EXPORT OF BOARD: {self.board.name}", expand=True, min_width=800)

        table.add_column("Board", justify="left", style="cyan", no_wrap=True)
        table.add_column("List", justify="right", style="cyan", no_wrap=True)
        table.add_column("Card", style="magenta", no_wrap=False)
        table.add_column("Labels", style="magenta", no_wrap=True)
        table.add_column("Due date", style="magenta", no_wrap=True)
        table.add_column("Checklist item name", no_wrap=False)
        table.add_column("URL Title", no_wrap=False)
        table.add_column("URL", no_wrap=False, overflow="fold")

        for row in rows:
            table.add_row(*row)

        self.console = Console(record=True)
        if print_console:
            self.console.print(table)

    def write_file(self, file):
        self.console.save_html(file)
        print("Generated rich table to: " + file)


class DataConverter:
    @staticmethod
    def convert_to_table_rows(board: TrelloBoard, card_filter_flags: CardFilter, header_len):
        rows = []
        for list in board.lists:
            cards = DataConverter.filter_cards(list, card_filter_flags)
            for card in cards:
                items: List[ExtractedCardData] = card.get_extracted_data(card_filter_flags)
                for item in items:
                    due_date = card.due_date if card.due_date else ""
                    # Board name, List name, Card name, card labels, card due date, Description, Attachment name, Attachment URL, Attachment Local URL, Attachment file path, Checklist item name, URL Title, URL
                    row = [board.name,
                           list.name,
                           card.name,
                           card.get_labels_as_str(),
                           due_date,
                           item.description,
                           item.attachment_name,
                           item.attachment_url,
                           item.local_server_path,
                           item.attachment_file_path,
                           item.cl_item_name,
                           item.cl_item_url_title,
                           item.cl_item_url]
                    if header_len != len(row):
                        raise ValueError("Mismatch in number of columns in row({}) vs. number of header columns ({})".format(len(row), header_len))
                    rows.append(row)
        return rows

    @staticmethod
    def filter_cards(list, card_filter_flags: CardFilter):
        if CardFilter.ALL() == card_filter_flags:
            return list.cards

        with_attachment = CardFilter.WITH_ATTACHMENT in card_filter_flags
        with_description = CardFilter.WITH_DESCRIPTION in card_filter_flags
        with_checklist = CardFilter.WITH_CHECKLIST in card_filter_flags

        filtered_cards = []
        for card in list.cards:
            keep = False
            if with_attachment and card.has_attachments:
                keep = True
            if with_description and card.has_description:
                keep = True
            if with_checklist and card.has_checklist:
                keep = True

            if keep:
                filtered_cards.append(card)
            else:
                print("Not keeping card: {}, filters: {}".format(card, card_filter_flags))

        return filtered_cards

    @staticmethod
    def get_header():
        h = TrelloBoardHtmlTableHeader
        # Board name, List name, Card name, card labels, card due date, Description, Attachment name, Attachment URL, Checklist item name, Checklist item URL Title, Checklist item URL
        header = [h.BOARD.value,
                  h.LIST.value,
                  h.CARD.value,
                  h.LABELS.value,
                  h.DUE_DATE.value,
                  h.DESCRIPTION.value,
                  h.ATTACHMENT_NAME.value,
                  h.ATTACHMENT_URL.value,
                  h.ATTACHMENT_LOCAL_URL.value,
                  h.ATTACHMENT_FILE__PATH.value,
                  h.CHECKLIST_ITEM_NAME.value,
                  h.CHECKLIST_ITEM_URL_TITLE.value,
                  h.CHECKLIST_ITEM_URL.value]
        return header

def load_webpage_title_cache() -> Dict[str, str]:
    with open(LocalDirsFiles.WEBPAGE_TITLE_CACHE_FILE, 'rb') as handle:
        try:
            return pickle.load(handle)
        except:
            return {}


def save_webpage_title_cache(data):
    with open(LocalDirsFiles.WEBPAGE_TITLE_CACHE_FILE, 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)


class OutputHandler:
    def __init__(self, board: TrelloBoard, html_gen_config):
        self.board = board
        self.html_file_gen = TrelloBoardHtmlFileGenerator(board, html_gen_config)
        self.html_table_gen = TrelloBoardHtmlTableGenerator(board)
        self.rich_table_gen = TrelloBoardRichTableGenerator(board)

        fname_prefix = f"trelloboard-{self.board.simple_name}"
        self.html_result_file_path = os.path.join(OUTPUT_DIR, f"{fname_prefix}-htmlexport.html")
        self.rich_table_file_path = os.path.join(OUTPUT_DIR, f"{fname_prefix}-rich-table.html")
        self.html_table_file_path = os.path.join(OUTPUT_DIR, f"{fname_prefix}-custom-table.html")
        self.csv_file_path = os.path.join(OUTPUT_DIR, f"{fname_prefix}.csv")
        self.csv_file_copy_to_file = f"~/Downloads/{fname_prefix}.csv"
        self.card_filter_flags = ACTIVE_CARD_FILTERS

    def write_outputs(self):
        header = DataConverter.get_header()
        rows = DataConverter.convert_to_table_rows(self.board, self.card_filter_flags, len(header))

        # Output 1: HTML file
        self.html_file_gen.render()
        self.html_file_gen.write_to_file(self.html_result_file_path)

        # TODO move this elsewhere?
        save_webpage_title_cache(webpage_title_cache)

        # Output 2: Rich table
        self.rich_table_gen.render(rows, print_console=False)
        self.rich_table_gen.write_file(self.rich_table_file_path)

        # Output 3: HTML table
        self.html_table_gen.render(rows, header)
        self.html_table_gen.write_file(self.html_table_file_path)

        # Output 4: CSV file
        if os.path.exists(self.csv_file_path):
            FileUtils.remove_file(self.csv_file_path)
        CsvFileUtils.append_rows_to_csv_file(self.csv_file_path, rows, header=header)
        print("Generated CSV file: " + self.csv_file_path)
        print(f"cp {self.csv_file_path} {self.csv_file_copy_to_file} && subl {self.csv_file_copy_to_file}")

def download_attachments(board):
    for list in board.lists:
        for card in list.cards:
            for attachment in card.attachments:
                if attachment.is_upload:
                    attachment.downloaded_file_path = "file://" + download_attachment(attachment)


def download_attachment(attachment):
    import shutil

    # https://community.developer.atlassian.com/t/update-authenticated-access-to-s3/43681
    response = requests.request(
        "GET",
        attachment.api_url,
        headers=TrelloUtils.authorization_headers
    )
    response.raise_for_status()
    file_path = os.path.join(OUTPUT_DIR_ATTACHMENTS, "{}-{}".format(attachment.id, attachment.file_name))

    # TODO Figure out why other 2 Methods resulted in 0-byte files?
    # Source: https://stackoverflow.com/a/13137873/1106893
    # Method 1
    # with open(file_path, 'wb') as out_file:
    #     shutil.copyfileobj(response.raw, out_file)

    # Method 2
    # if response.status_code == 200:
    #     with open(file_path, 'wb') as f:
    #         response.raw.decode_content = True
    #         shutil.copyfileobj(response.raw, f)

    # Method 3
    r = response
    path = file_path
    if r.status_code == 200:
        with open(path, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)

    del response
    return file_path

def launch_http_server(dir):
    import http.server
    import socketserver

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=dir, **kwargs)

    #Handler = http.server.SimpleHTTPRequestHandler

    with socketserver.TCPServer(("", HTTP_SERVER_PORT), Handler) as httpd:
        HTTP_SERVER_INSTANCE = httpd
        print("serving at port", HTTP_SERVER_PORT)
        httpd.serve_forever()
        httpd.shutdown()


def stop_server():
    if config.serve_attachments:
        HTTP_SERVER_INSTANCE.shutdown()


def get_board_id(board_name):
    # board_resp = get_board()
    # print(json.dumps(json.loads(board_resp.text), sort_keys=True, indent=4, separators=(",", ": ")))
    boards = list_boards()
    available_board_names = list(boards.keys())
    print(f"Available boards: {available_board_names}")
    if board_name not in boards:
        raise KeyError(f"Cannot find board with name: {board_name}")

    board_id = boards[board_name]
    return board_id


if __name__ == '__main__':
    atexit.register(stop_server)

    validate_config()
    html_gen_config = TRELLO_CARD_GENERATOR_BASIC_CONFIG

    FileUtils.ensure_dir_created(OUTPUT_DIR)
    FileUtils.ensure_dir_created(OUTPUT_DIR_ATTACHMENTS)

    board_name = 'CLOUDERA: Planning'
    board_id = get_board_id(board_name)

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

    webpage_title_cache = load_webpage_title_cache()
    board = TrelloBoard(board_id, board_name, trello_lists_open)
    board.get_checklist_url_titles()

    # Download attachments
    download_attachments(board)

    out = OutputHandler(board, html_gen_config)
    out.write_outputs()

    # Serve attachment files for CSV output
    if config.serve_attachments:
        launch_http_server(dir=OUTPUT_DIR_ATTACHMENTS)


    # TODO IDEA: HTML output file per list,
    #  only include: card name (bold), description (plain text), Checklists with check items
    #  Add WARNING text if has attachment OR add attachment links

    # TODO add file cache that stores in the following hierarchy:
    #  <maindir>/boards/<board>/cards/<card>/actions/<action_id>.json

