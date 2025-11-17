import logging
import os
import pickle
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

import requests
from pythoncommons.file_utils import FileUtils, CsvFileUtils
from pythoncommons.result_printer import TableRenderingConfig, ResultPrinter, TabulateTableFormat

from trello_backup.display.console import CliLogger
from trello_backup.constants import FilePath
from trello_backup.trello.api import TrelloApi, TrelloUtils
from trello_backup.trello.model import TrelloComment, TrelloList, TrelloAttachment, TrelloChecklistItem, \
    TrelloChecklist, TrelloCard, TrelloBoard, ExtractedCardData, CardFilter

INDENT = "&nbsp;&nbsp;&nbsp;&nbsp;"



LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)

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

CARD_FILTER_ALL = CardFilter.ALL()
CARD_FILTER_DESC_AND_CHECKLIST = CardFilter.WITH_DESCRIPTION | CardFilter.WITH_CHECKLIST
CARD_FILTER_DESC_AND_ATTACHMENT = CardFilter.WITH_DESCRIPTION | CardFilter.WITH_ATTACHMENT
CARD_FILTER_CHECKLIST_AND_ATTACHMENT = CardFilter.WITH_CHECKLIST | CardFilter.WITH_ATTACHMENT
CARD_FILTER_ONLY_DESC = CardFilter.WITH_DESCRIPTION

ACTIVE_CARD_FILTERS = CARD_FILTER_ALL


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
    try:
        with open(FilePath.WEBPAGE_TITLE_CACHE_FILE, 'rb') as handle:
            return pickle.load(handle)
    except:
        return {}


def save_webpage_title_cache(data):
    with open(FilePath.WEBPAGE_TITLE_CACHE_FILE, 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)


class OutputHandler:
    def __init__(self, board: TrelloBoard, html_gen_config):
        self.board = board
        self.html_file_gen = TrelloBoardHtmlFileGenerator(board, html_gen_config)
        self.html_table_gen = TrelloBoardHtmlTableGenerator(board)
        self.rich_table_gen = TrelloBoardRichTableGenerator(board)

        fname_prefix = f"trelloboard-{self.board.simple_name}"
        self.html_result_file_path = os.path.join(FilePath.TRELLO_OUTPUT_DIR, f"{fname_prefix}-htmlexport.html")
        self.rich_table_file_path = os.path.join(FilePath.TRELLO_OUTPUT_DIR, f"{fname_prefix}-rich-table.html")
        self.html_table_file_path = os.path.join(FilePath.TRELLO_OUTPUT_DIR, f"{fname_prefix}-custom-table.html")
        self.csv_file_path = os.path.join(FilePath.TRELLO_OUTPUT_DIR, f"{fname_prefix}.csv")
        self.csv_file_copy_to_file = f"~/Downloads/{fname_prefix}.csv"
        self.card_filter_flags = ACTIVE_CARD_FILTERS

    def write_outputs(self):
        header = DataConverter.get_header()
        rows = DataConverter.convert_to_table_rows(self.board, self.card_filter_flags, len(header))

        # Output 1: HTML file
        self.html_file_gen.render()
        self.html_file_gen.write_to_file(self.html_result_file_path)

        # TODO move this elsewhere?
        # TODO remove
        from trello_backup.cmd_handler import webpage_title_cache
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
    # https://community.developer.atlassian.com/t/update-authenticated-access-to-s3/43681
    response = requests.request(
        "GET",
        attachment.api_url,
        headers=TrelloUtils.authorization_headers
    )
    response.raise_for_status()
    file_path = os.path.join(FilePath.OUTPUT_DIR_ATTACHMENTS, "{}-{}".format(attachment.id, attachment.file_name))

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


if __name__ == '__main__':
    raise NotImplementedError()
