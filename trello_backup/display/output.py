import os
from dataclasses import dataclass
from enum import Enum
from io import StringIO
from typing import List, Dict, Any

from markdown import Markdown
from pythoncommons.file_utils import FileUtils, CsvFileUtils
from pythoncommons.result_printer import TabulateTableFormat, TableRenderingConfig, ResultPrinter
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from trello_backup.constants import FilePath
from trello_backup.display.console import ConsoleUtils
from trello_backup.trello.filter import CardFilterer
from trello_backup.trello.model import TrelloComment, TrelloChecklist, TrelloBoard, CardFilter, ExtractedCardData, \
    CardFilters, TrelloLists

INDENT = "&nbsp;&nbsp;&nbsp;&nbsp;"

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
        converted2 = (converted.encode('ascii', 'ignore')).decode("utf-8")
        return converted2



class TrelloDataConverter:
    def __init__(self, md_formatter: 'MarkdownFormatter', http_server_port: int):
        self._md_formatter = md_formatter
        self._http_server_port = http_server_port

    def convert_to_output_data(self, trello_lists: TrelloLists) -> List[Dict[str, Any]]:
        output_data = []
        for list_name, list_obj in trello_lists.by_name.items():
            list_data = {
                "name": list_name,
                "cards": []
            }

            for card in list_obj.cards:
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
                    ]
                }
                list_data["cards"].append(card_data)

            output_data.append(list_data)
        return output_data

    def convert_to_table_rows(self, board: TrelloBoard, card_filter_flags: CardFilter, header_len, md_formatter) -> List[List[str]]:
        rows = []
        for list in board.lists:
            cards = CardFilterer.filter_cards(list, card_filter_flags)
            for card in cards:
                items: List[ExtractedCardData] = card.get_extracted_data(card_filter_flags, md_formatter)
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

    def get_header(self):
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
        print("Generated HTML file output to: " + file)



class OutputHandler:
    def __init__(self, data_converter: TrelloDataConverter, board: TrelloBoard, html_gen_config):
        self.board = board
        self._data_converter = data_converter
        self._set_file_paths()
        self._set_generators(board, html_gen_config)
        self._md_formatter = MarkdownFormatter()

    def _set_file_paths(self):
        fname_prefix = f"trelloboard-{self.board.simple_name}"
        output_dir = FilePath.TRELLO_OUTPUT_DIR
        self.html_result_file_path = os.path.join(output_dir, f"{fname_prefix}-htmlexport.html")
        self.rich_table_file_path = os.path.join(output_dir, f"{fname_prefix}-rich-table.html")
        self.html_table_file_path = os.path.join(output_dir, f"{fname_prefix}-custom-table.html")
        self.csv_file_path = os.path.join(output_dir, f"{fname_prefix}.csv")
        self.csv_file_copy_to_file = f"~/Downloads/{fname_prefix}.csv"

    def _set_generators(self, board, html_gen_config):
        self.html_file_gen = TrelloBoardHtmlFileGenerator(board, html_gen_config)
        self.html_table_gen = TrelloBoardHtmlTableGenerator(board)
        self.rich_table_gen = TrelloBoardRichTableGenerator(board, print_to_console=False)

        self._generators = [
            (self.html_file_gen, self.html_result_file_path),
            (self.html_table_gen, self.html_table_file_path),
            (self.rich_table_gen, self.rich_table_file_path),
        ]

    def write_outputs(self):
        header = self._data_converter.get_header()
        rows = self._data_converter.convert_to_table_rows(self.board, CardFilters.ALL.value, len(header), self._md_formatter)

        # Outputs: HTML file, HTML table, Rich table
        for generator, path in self._generators:
            # Assuming all generators have a compatible render signature
            generator.render(rows, header)
            generator.write_file(path)

        # Handle CSV separately due to unique logic (removal, printing)
        self._generate_csv_file(header, rows)

    def _generate_csv_file(self, header: list[str | Any], rows: list[Any]):
        if os.path.exists(self.csv_file_path):
            FileUtils.remove_file(self.csv_file_path)
        CsvFileUtils.append_rows_to_csv_file(self.csv_file_path, rows, header=header)
        print("Generated CSV file: " + self.csv_file_path)
        print(f"cp {self.csv_file_path} {self.csv_file_copy_to_file} && subl {self.csv_file_copy_to_file}")


class OutputHandlerFactory:
    @staticmethod
    def create_for_board(data_converter: TrelloDataConverter, board: TrelloBoard, html_gen_config: TrelloCardHtmlGeneratorMode) -> OutputHandler:
        return OutputHandler(data_converter, board, html_gen_config)



class TrelloBoardRichTableGenerator:
    def __init__(self, board, print_to_console=False):
        self._board = board
        self._console = ConsoleUtils.create_console(record=True, log_to_console=print_to_console)

    def render(self, rows, header):
        # TODO implement console mode --> Just print this and do not log anything to console other than the table
        from rich.table import Table
        table = Table(title=f"TRELLO EXPORT OF BOARD: {self._board.name}", expand=True, min_width=800)

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

        self._console.print(table)

    def write_file(self, file):
        self._console.save_html(file)
        print("Generated rich table to: " + file)

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
                console.print("[i]No cards found in this list.[/i]")
                print("\n")
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

        print("\n")

    @staticmethod
    def print_plain_text(trello_data: List[Dict[str, Any]], print_placeholders=False, only_open=False):
        # TODO ASAP Apply CardFilters
        for list_obj in trello_data:
            #for name, list in trello_lists.by_name.items():
            print(f"List: {list_obj['name']}")
            for card in list_obj["cards"]:
                if only_open and card["closed"]:
                    continue
                print(f"CARD: {card['name']}")
                print("DESCRIPTION:")
                if card['description']:
                    print(f"{card['description']}")
                else:
                    if print_placeholders:
                        print("<EMPTY>")

                if print_placeholders and not card["checklists"]:
                    print("<NO CHECKLISTS>")
                print()
                for checklist in card["checklists"]:
                    print(f"{checklist['name']} ({len(checklist['items'])}): ")
                    for item in checklist['items']:
                        # sanity check
                        if item['url'] and not item['url_title']:
                            raise ValueError(f"CLI should have URL title if URL is parsed. CLI details: {item}")
                        if item['url']:
                            print(f"[{'x' if item['checked'] else ''}] {item['url_title']}: {item['url']}")
                        else:
                            print(f"[{'x' if item['checked'] else ''}] {item['value']}")
                print("=" * 60) # Separator for cards


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
            print(f"Generated HTML table to file: {file}")

