import enum
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from io import StringIO
from typing import List, Dict, Any, Tuple, Callable, Iterable

from markdown import Markdown
from pythoncommons.file_utils import FileUtils, CsvFileUtils
from pythoncommons.result_printer import TabulateTableFormat, TableRenderingConfig, ResultPrinter
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from trello_backup.display.console import ConsoleUtils, CliLogger
from trello_backup.display.table import TrelloTable, TrelloTableRenderSettings, TrelloTableColumnStyles
from trello_backup.exception import TrelloException
from trello_backup.http_server import HTTP_SERVER_PORT
from trello_backup.trello.filter import CardFilterer, CardFilters, CardPropertyFilter, TrelloFilters
from trello_backup.trello.model import TrelloComment, TrelloChecklist, TrelloBoard, ExtractedCardData, \
    TrelloLists, TrelloCard, TrelloList

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


INDENT = "&nbsp;&nbsp;&nbsp;&nbsp;"

class TableHeaderFieldName(Enum):
    BOARD = "Board"
    LIST = "List"
    CARD = "Card"
    LABELS = "Labels"
    DUE_DATE = "Due date"
    DESCRIPTION = "Description"
    ATTACHMENT_NAME = "Attachment name"
    ATTACHMENT_URL = "Attachment URL"
    ATTACHMENT_LOCAL_URL = "Attachment Local URL"
    ATTACHMENT_FILE_PATH = "Attachment File path"
    CHECKLIST_ITEM_NAME = "Checklist item Name"
    CHECKLIST_ITEM_URL_TITLE = "Checklist item URL Title"
    CHECKLIST_ITEM_URL = "Checklist item URL"



class TableHeader:
    def __init__(self, cols: List[TableHeaderFieldName]):
        self._cols = cols

    def __len__(self):
        return len(self._cols)

    def as_string_headers(self):
        return [c.value for c in self._cols]

    def cols_set(self):
        return set(self._cols)

    def cols_list(self):
        return list(self._cols)


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


class TrelloCardHtmlGeneratorMode(Enum):
    MINIMAL = TrelloCardHtmlGeneratorConfig(include_labels=False,
                                            include_due_date=False,
                                            include_checklists=True,
                                            include_activity=False,
                                            include_comments=False)
    BASIC = TrelloCardHtmlGeneratorConfig(include_labels=True,
                                          include_due_date=True,
                                          include_checklists=True,
                                          include_activity=False,
                                          include_comments=False)
    FULL = TrelloCardHtmlGeneratorConfig(include_labels=True,
                                         include_due_date=True,
                                         include_checklists=True,
                                         include_activity=True,
                                         include_comments=True)


class MarkdownFormatter:
    def __init__(self):
        # patching Markdown
        Markdown.output_formats["plain"] = MarkdownFormatter.unmark_element
        self.__md = Markdown(output_format="plain")
        self.__md.stripTopLevelTags = False

    @staticmethod
    def unmark_element(element, stream=None):
        """
            https://stackoverflow.com/a/54923798/1106893
        """
        if stream is None:
            stream = StringIO()
        if element.text:
            stream.write(element.text)
        for sub in element:
            MarkdownFormatter.unmark_element(sub, stream)
        if element.tail:
            stream.write(element.tail)
        return stream.getvalue()

    def to_plain_text(self, text):
        converted = self.__md.convert(text)

        # Remove potential ZWNJ (0x200c) characters: https://unicodemap.org/details/0x200C/index.html
        # Remove only ZWNJ (U+200C), keep other Unicode
        converted = converted.replace("\u200c", "")
        # Uncomment this if we want ASCII characters only
        # converted2 = (converted.encode('ascii', 'ignore')).decode("utf-8")
        return converted



class TrelloDataConverter:
    def __init__(self, md_formatter: 'MarkdownFormatter', http_server_port: int):
        self._md_formatter = md_formatter
        self._http_server_port = http_server_port
        h = TableHeaderFieldName
        # Board name, List name, Card name, card labels, card due date, Description, Attachment name, Attachment URL, Checklist item name, Checklist item URL Title, Checklist item URL
        self._header = TableHeader([h.BOARD,
                  h.LIST,
                  h.CARD,
                  h.LABELS,
                  h.DUE_DATE,
                  h.DESCRIPTION,
                  h.ATTACHMENT_NAME,
                  h.ATTACHMENT_URL,
                  h.ATTACHMENT_LOCAL_URL,
                  h.ATTACHMENT_FILE_PATH,
                  h.CHECKLIST_ITEM_NAME,
                  h.CHECKLIST_ITEM_URL_TITLE,
                  h.CHECKLIST_ITEM_URL])
        self._col_value_getters = {
            h.BOARD: lambda board, list, card, item: board.name,
            h.LIST: lambda board, list, card, item: list.name,
            h.CARD: lambda board, list, card, item: card.name,
            h.LABELS: lambda board, list, card, item: card.get_labels_as_str(),
            h.DUE_DATE: lambda board, list, card, item: card.due_date if card.due_date else "",
            h.DESCRIPTION: lambda board, list, card, item: item.description,
            h.ATTACHMENT_NAME: lambda board, list, card, item: item.attachment_name,
            h.ATTACHMENT_URL: lambda board, list, card, item: item.attachment_url,
            h.ATTACHMENT_LOCAL_URL: lambda board, list, card, item: item.local_server_path,
            h.ATTACHMENT_FILE_PATH: lambda board, list, card, item: item.attachment_file_path,
            h.CHECKLIST_ITEM_NAME: lambda board, list, card, item: item.cl_item_name,
            h.CHECKLIST_ITEM_URL_TITLE: lambda board, list, card, item: item.cl_item_url_title,
            h.CHECKLIST_ITEM_URL: lambda board, list, card, item: item.cl_item_url
        }
        self._sanity_check_col_value_getters()
        self._none_value_converters = {h.CHECKLIST_ITEM_URL_TITLE: lambda val: ""}

    def _sanity_check_col_value_getters(self):
        cols_set = self._header.cols_set()
        missing_getters = []
        for col in cols_set:
            if col not in self._col_value_getters:
                missing_getters.append(col)

        if missing_getters:
            raise TrelloException(
                f"Value getters are not configured for the following columns: {', '.join([g.value for g in missing_getters])}")

    def convert_to_output_data(self, trello_lists: TrelloLists) -> List[Dict[str, Any]]:
        output_data = []
        for trello_list in trello_lists.get():
            list_data = self.convert_list_to_output(trello_list.name, trello_list)
            output_data.append(list_data)
        return output_data

    def convert_list_to_output(self, list_name: str, trello_list: TrelloList):
        list_data = {
            "name": list_name,
            "cards": []
        }

        for card in trello_list.cards:
            card_data = self.convert_card_to_output(card)
            list_data["cards"].append(card_data)
        return list_data

    def convert_card_to_output(self, card: TrelloCard):
        # Structure the card data, including converting markdown
        card_data = {
            "id": card.id,
            "name": card.name,
            "closed": card.closed,
            "description": self._md_formatter.to_plain_text(card.description),
            "attachments": [
                {
                    "name": a.name,
                    "url": a.url,
                    "local_path": a.downloaded_file_path,
                    "local_server_path": f"http://localhost:{self._http_server_port}/{a.downloaded_file_path.split('/')[-1]}" if a.downloaded_file_path else ""
                } for a in card.attachments
            ],
            "checklists": [
                {
                    "name": cl.name,
                    "items": [
                        {"value": cli.value, "url": cli.url, "url_title": cli.url_title, "checked": cli.checked}
                        for cli in cl.items
                    ]
                } for cl in card.checklists
            ],
            "labels": card.labels
        }
        return card_data

    def convert_to_table_rows(self, board: TrelloBoard, filters: TrelloFilters, md_formatter) -> Tuple[List[List[str]], List[str]]:
        rows = []
        for list in board.lists:
            cards = CardFilterer.filter_cards(list, filters.card_filters)
            for card in cards:
                items: List[ExtractedCardData] = self._extract_card_data(card, filters.card_filters, md_formatter)
                for item in items:
                    row = []
                    for col in self._header.cols_list():
                        val = self._col_value_getters[col](board, list, card, item)
                        if val is None:
                            if col in self._none_value_converters:
                                val = self._none_value_converters[col](val)
                            else:
                                raise ValueError(f"Value is None for column: {col}")
                        row.append(val)
                    if len(self._header) != len(row):
                        raise ValueError("Mismatch in number of columns in row({}) vs. number of header columns ({})".format(len(row), self._header))
                    rows.append(row)
        return rows, self._header.as_string_headers()

    def _extract_card_data(self, card, card_filters, md_formatter):
        # TODO ASAP Filtering cleanup
        # TODO ASAP code cleanup
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
        plain_text_description = md_formatter.to_plain_text(card.description)
        result = []

        card_prop_flags = card_filters.value
        if len(card_prop_flags) == 1 and CardPropertyFilter.WITH_DESCRIPTION in card_prop_flags:
            result.append(ExtractedCardData(plain_text_description, "", "", "", "", "", "", ""))
            return result

        # 2. Add attachments to separate row from checklist items
        if CardPropertyFilter.WITH_ATTACHMENT in card_prop_flags:
            for attachment in card.attachments:
                attachment_file_path = "" if not attachment.downloaded_file_path else attachment.downloaded_file_path

                local_server_path = ""
                if attachment.downloaded_file_path:
                    # TODO ASAP refactor Separation of concerns
                    local_server_path = "http://localhost:{}/{}".format(HTTP_SERVER_PORT, attachment.downloaded_file_path.split("/")[-1])
                result.append(ExtractedCardData(plain_text_description, attachment.name, attachment.url, attachment_file_path, local_server_path, "", "", ""))

        # 3. Add checklist items to separate row from attachments
        if CardPropertyFilter.WITH_CHECKLIST in card_prop_flags:
            for cl in card.checklists:
                for item in cl.items:
                    cl_item_name = ""
                    cl_item_url_title = ""
                    cl_item_url = ""
                    if item.url:
                        cl_item_url_title = item.url_title
                        cl_item_url = item.url
                    else:
                        cl_item_name = item.value
                    result.append(ExtractedCardData(plain_text_description, "", "", "", "", cl_item_name, cl_item_url_title, cl_item_url))

        # If no append happened, append default ExtractedCardData
        if not result and CardPropertyFilter.WITH_DESCRIPTION in card_prop_flags:
            result.append(ExtractedCardData(plain_text_description, "", "", "", "", "", "", ""))
        return result



class TrelloBoardHtmlFileGenerator:
    def __init__(self, board, config):
        self._board = board
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
        if not card.description:
            return ""
        desc = card.description
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

    def render(self, rows, header):
        """
        Accept rows and header parameters to conform with other Trello output renderer interfaces
        """
        html = self.default_style
        for trello_list in self._board.lists:
            html += f"<h1>LIST: {trello_list.name} ({len(trello_list.cards)} cards)</h1><br><br>"
            for card in trello_list.cards:
                html += self._render_card(trello_list, card)
        self.html = html

    def write_file(self, file):
        FileUtils.write_to_file(file, self.html)

class OutputType(enum.Enum):
    HTML_FILE = "html file"
    RICH_HTML_TABLE = "rich html table"
    CUSTOM_HTML_TABLE = "custom html table"
    CSV = "csv"
    BOARD_JSON = "board json"


class OutputHandler:
    def __init__(self,
                 data_converter: TrelloDataConverter,
                 output_dir: str,
                 board: TrelloBoard,
                 html_gen_config,
                 filters: TrelloFilters):
        self._data_converter = data_converter
        self._output_dir = output_dir
        self.board = board
        self._set_file_paths()
        self._set_generators(board, html_gen_config)
        self._md_formatter = MarkdownFormatter()
        self._filters: TrelloFilters = filters
        self._callback_gen_files: Callable[[str, str], None] = None

    def _set_file_paths(self):
        fname_prefix = f"board-{self.board.simple_name}"
        self._output_file_paths = {
            OutputType.HTML_FILE: os.path.join(self._output_dir, f"{fname_prefix}.html"),
            OutputType.RICH_HTML_TABLE: os.path.join(self._output_dir, f"{fname_prefix}-rich-table.html"),
            OutputType.CUSTOM_HTML_TABLE: os.path.join(self._output_dir, f"{fname_prefix}-custom-table.html"),
            OutputType.CSV: os.path.join(self._output_dir, f"{fname_prefix}.csv"),
            OutputType.BOARD_JSON: os.path.join(self._output_dir, f"{fname_prefix}.json"),
        }

    def _set_generators(self, board, html_gen_config):
        self._generators: Dict[OutputType, Any] = {
            OutputType.HTML_FILE: TrelloBoardHtmlFileGenerator(board, html_gen_config),
            OutputType.CUSTOM_HTML_TABLE: TrelloBoardHtmlTableGenerator(board),
            OutputType.RICH_HTML_TABLE: TrelloBoardRichTableGenerator(board, print_to_console=False),
        }

    @staticmethod
    def get_board_filename_by_board(board):
        return f"board-{board.simple_name}.json"

    def write_outputs(self, board_name: str, callback: Callable[[OutputType, str], None]):
        self._callback_gen_files: Callable[[OutputType, str], None] = callback

        header: List[str]
        rows, header = self._data_converter.convert_to_table_rows(self.board, self._filters, self._md_formatter)

        # Outputs: HTML file, HTML table, Rich table
        for type, generator in self._generators.items():
            file_path = self._output_file_paths[type]
            # Assuming all generators have a compatible render signature
            generator.render(rows, header)
            generator.write_file(file_path)
            self._callback_gen_files(board_name, type, file_path)

        # Handle these output types separately due to unique logic (removal, printing)
        self._generate_csv_file(board_name, header, rows)
        self._write_board_json(board_name)

    # TODO ASAP Consider migrating these to generator classes
    def _generate_csv_file(self, board_name, header: list[str | Any], rows: list[Any]):
        file_path = self._output_file_paths[OutputType.CSV]
        if os.path.exists(file_path):
            FileUtils.remove_file(file_path)
        CsvFileUtils.append_rows_to_csv_file(file_path, rows, header=header)
        self._callback_gen_files(board_name, OutputType.CSV, file_path)

    def _write_board_json(self, board_name):
        # Uncomment this for other JSON printout
        # print(json.dumps(parsed_json, sort_keys=True, indent=4, separators=(",", ": ")))

        file_path = self._output_file_paths[OutputType.BOARD_JSON]
        with open(file_path, "w") as f:
            json.dump(self.board.json, f, indent=4)
        self._callback_gen_files(board_name, OutputType.BOARD_JSON, file_path)


class OutputHandlerFactory:
    @staticmethod
    def create_for_board(data_converter: TrelloDataConverter,
                         backup_dir: str,
                         board: TrelloBoard,
                         html_gen_config: TrelloCardHtmlGeneratorMode,
                         filters: TrelloFilters) -> OutputHandler:
        return OutputHandler(data_converter, backup_dir, board, html_gen_config, filters)



class TrelloBoardRichTableGenerator:
    def __init__(self, board, print_to_console=False):
        self._board = board
        self._console = ConsoleUtils.create_console(record=True, log_to_console=print_to_console, wide=True)

    def render(self, rows, header: List[str]):
        # TODO implement console mode --> Just print this and do not log anything to console other than the table

        # white color is just dummy for empty cells - Not really important
        col_styles = TrelloTableColumnStyles()
        (col_styles
         .bind_style(TableHeaderFieldName.BOARD.value, "", "white", {"justify": "left", "style": "cyan", "no_wrap": True})
         .bind_style(TableHeaderFieldName.LIST.value, "", "white", {"justify": "right", "style": "cyan", "no_wrap": True})
         .bind_style(TableHeaderFieldName.CARD.value, "", "white", {"style": "magenta", "no_wrap": False})
         .bind_style(TableHeaderFieldName.LABELS.value, "", "white", {"style": "magenta", "no_wrap": True})
         .bind_style(TableHeaderFieldName.DUE_DATE.value, "", "white", {"style": "magenta", "no_wrap": True})
         .bind_style(TableHeaderFieldName.CHECKLIST_ITEM_NAME.value, "", "white", {"no_wrap": False})
         .bind_style(TableHeaderFieldName.CHECKLIST_ITEM_URL_TITLE.value, "", "white", {"no_wrap": False})
         .bind_style(TableHeaderFieldName.CHECKLIST_ITEM_URL.value, "", "white", {"overflow": "fold", "no_wrap": False})
         )
        render = TrelloTableRenderSettings(col_styles,
                                           wide_print=True,
                                           show_lines=True,
                                           additional_table_config={"expand": True, "min_width": 800})
        table = TrelloTable(header, render, title=f"TRELLO EXPORT OF BOARD: {self._board.name}")
        table.render(rows)
        self._console.print(table._table)

    def write_file(self, file):
        self._console.save_html(file)

class TrelloListAndCardsPrinter:
    @staticmethod
    def print_rich(trello_data: List[Dict[str, Any]]):
        """
        Prints the structured Trello data using the rich library for nice formatting.
        """
        console = Console()

        # Define styles for reuse
        list_style = Style(color="cyan", bold=True, reverse=True)
        card_style = Style(color="green", bold=True)
        header_style = Style(color="yellow", bold=True)

        for list_obj in trello_data:
            list_name = list_obj["name"]

            # Print List Header
            console.rule(Text(f" Trello List: {list_name} ", style=list_style))

            if not list_obj["cards"]:
                console.print("[i]No cards found in this list.[/i]\n")
                continue

            for card in list_obj["cards"]:
                # Print Card Header
                console.print(f"\n[b]📌 Card:[/b] [bold green]{card['name']}[/bold green]", style=card_style)

                # Print Description (if available)
                if card["description"]:
                    console.print(f"\n[b]📝 Description:[/b]")
                    console.print(f"[italic]{card['description']}[/italic]")

                # Print Attachments
                if card["attachments"]:
                    attachment_table = Table(title=Text("Attachments", style=header_style), show_header=True, header_style="magenta", show_lines=True)
                    attachment_table.add_column("Name", style="dim", overflow="fold")
                    attachment_table.add_column("URL", style="blue", overflow="fold")
                    attachment_table.add_column("Local Server Link", style="green", overflow="fold")

                    for a in card["attachments"]:
                        local_link = Text(a["local_server_path"] or "N/A", style="link " + ("bold blue" if a["local_server_path"] else "dim"))
                        attachment_table.add_row(
                            a["name"],
                            a["url"],
                            local_link
                        )
                    console.print(attachment_table)

                # Print Checklists
                if card["checklists"]:
                    for checklist in card["checklists"]:
                        cl_table = Table(title=Text(f"Checklist: {checklist['name']}", style=header_style), show_header=True, header_style="red", show_lines=False)
                        cl_table.add_column("Status", width=10, style="bold")
                        cl_table.add_column("Item / Title", style="bold", overflow="fold")
                        cl_table.add_column("URL", style="blue", overflow="fold")

                        for item in checklist["items"]:
                            status = "[bold green]✓[/bold green]" if item["checked"] else "[bold red]✗[/bold red]"

                            # Use the URL title if available, otherwise use the item name
                            item_text = item["url_title"] if item["url_title"] else item["value"]
                            url_text = Text(item["url"] or "N/A", style="link " + ("blue" if item["url"] else "dim"))

                            cl_table.add_row(status, item_text, url_text)

                        console.print(cl_table)

                console.print("-" * 60) # Separator for cards

        console.print("\n")

    @staticmethod
    def print_plain_text(trello_data: List[Dict[str, Any]], print_placeholders=False, only_open=False):
        for list_obj in trello_data:
            TrelloListAndCardsPrinter.print_list_plain_text(list_obj, only_open, print_placeholders)

    @staticmethod
    def print_list_plain_text(list_obj: dict[str, Any], only_open: bool, print_placeholders: bool):
        CLI_LOG.info(f"List: {list_obj['name']}")
        for card in list_obj["cards"]:
            # TODO ASAP filtering Apply CardFilters elsewhere!
            if only_open and card["closed"]:
                continue
            TrelloListAndCardsPrinter.print_card_plain_text(card, print_placeholders)

    @staticmethod
    def print_card_plain_text(card, print_placeholders: bool):
        CLI_LOG.info("=" * 60)  # Separator for cards
        CLI_LOG.info(f"CARD: {card['name']}")
        labels_str = ", ".join(card['labels'])
        CLI_LOG.info(f"Labels: {labels_str}")
        CLI_LOG.info("DESCRIPTION:")
        if card['description']:
            CLI_LOG.info(f"{card['description']}")
        else:
            if print_placeholders:
                CLI_LOG.info("<EMPTY>")

        if print_placeholders and not card["checklists"]:
            CLI_LOG.info("<NO CHECKLISTS>")
        CLI_LOG.info("\n")
        for checklist in card["checklists"]:
            CLI_LOG.info(f"{checklist['name']} ({len(checklist['items'])}): ")
            for item in checklist['items']:
                checked_info = f"[{'x' if item['checked'] else ''}]"
                if item['url'] and item['url_title']:
                    CLI_LOG.info(f"{checked_info} {item['url_title']}: {item['url']}")
                elif item['url']:
                    CLI_LOG.info(f"{checked_info} {item['url']}")
                else:
                    CLI_LOG.info(f"{checked_info} {item['value']}")
            CLI_LOG.info("")
        CLI_LOG.info("=" * 60)  # Separator for cards


class TrelloBoardHtmlTableGenerator:
    DEFAULT_TABLE_FORMATS = [TabulateTableFormat.HTML]

    def __init__(self, board):
        self._tables = {}

    def render(self, rows, header):
        render_conf = TableRenderingConfig(
            row_callback=lambda row: row,
            print_result=False,
            max_width=200,
            max_width_separator=os.sep,
            tabulate_formats=TrelloBoardHtmlTableGenerator.DEFAULT_TABLE_FORMATS,
        )
        self._tables: Dict[TabulateTableFormat, str] = ResultPrinter.print_tables(
            data=rows,
            header=header,
            render_conf=render_conf,
        )

    def write_file(self, file):
        for fmt, table in self._tables.items():
            FileUtils.save_to_file(file, table)


class BackupReport:
    def __init__(self):
        self._generated_files: defaultdict[str, defaultdict[OutputType, List[str]]] = \
            defaultdict(lambda: defaultdict(list))

    def file_write_callback(self, board_name: str, file_type: OutputType, file_path: str):
        self._generated_files[board_name][file_type].append(file_path)
        # if file_type in self._generated_files:
        #     raise ValueError(f"File type {file_type} is already generated as {self._generated_files[file_type]}. Preventing overwrites!")

    def get_files(self, file_type: OutputType) -> Iterable[str]:
        """
        Returns an iterable of all file paths across all boards for a given OutputType.
        """
        # Use a generator expression for memory efficiency
        return (
            file_path
            for board_files in self._generated_files.values() # Iterate over the inner dicts (value for each board)
            if file_type in board_files                      # Check if the board has files of this type
            for file_path in board_files[file_type]           # Yield each file path for that type
        )

    def print(self):
        """
        Prints all generated files, categorized by board name and output type.
        """
        for board_name, board_files in self._generated_files.items():
            if not board_files:
                continue # Skip boards with no generated files

            CLI_LOG.info("--- 📂 Report for Board: %s ---", board_name)
            for out_type, filenames in board_files.items():
                # Print each filename on a new line for clarity
                for filename in filenames:
                    CLI_LOG.info("Generated %s file: %s", out_type.value, filename)
