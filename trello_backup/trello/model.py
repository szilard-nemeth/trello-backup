from dataclasses import dataclass, field
from enum import Flag, auto, Enum
from typing import List, Dict

from pythoncommons.url_utils import UrlUtils

from trello_backup.http_server import HTTP_SERVER_PORT
from trello_backup.trello.cache import WebpageTitleCache
from trello_backup.trello.html import HtmlParser

# TODO ASAP Extract any parsing logic from dataclasses

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


# TODO ASAP Move this to some other module?
class CardFilter(Flag):
    NONE = 0
    OPEN = auto()  # TODO ASAP Apply this card filter
    WITH_CHECKLIST = auto()
    WITH_DESCRIPTION = auto()
    WITH_ATTACHMENT = auto()

    @classmethod
    def ALL(cls):
        retval = cls.NONE
        for member in cls.__members__.values():
            retval |= member
        return retval


class CardFilters(Enum):
    ALL = CardFilter.ALL()
    DESC_AND_CHECKLIST = CardFilter.WITH_DESCRIPTION | CardFilter.WITH_CHECKLIST
    DESC_AND_ATTACHMENT = CardFilter.WITH_DESCRIPTION | CardFilter.WITH_ATTACHMENT
    CHECKLIST_AND_ATTACHMENT = CardFilter.WITH_CHECKLIST | CardFilter.WITH_ATTACHMENT
    ONLY_DESCRIPTION = CardFilter.WITH_DESCRIPTION



@dataclass
class TrelloComment:
    id: str
    author: str
    date: str
    contents: str


@dataclass
class TrelloList:
    closed: bool
    id: str
    name: str
    board_id: str
    cards: List['TrelloCard'] = field(default_factory=list)


class TrelloLists:
    def __init__(self, board_json):
        from trello_backup.trello.controller import TrelloObjectParser
        trello_lists_all: List[TrelloList] = TrelloObjectParser.parse_trello_lists(board_json)

        self.by_id: Dict[str, TrelloList] = {l.id: l for l in trello_lists_all}
        # Filter open trello lists
        self.open: List[TrelloList] = list(filter(lambda tl: not tl.closed, trello_lists_all))


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

    def get_url_titles(self, cache: WebpageTitleCache):
        import re
        for item in self.items:
            try:
                url = UrlUtils.extract_from_str(item.name)
            except:
                url = None
            if url:
                cached_title = cache.get(url)
                if not cached_title:
                    # Fetch title of URL
                    url_title = HtmlParser.get_title_from_url(url)
                    url_title = re.sub(r'[\n\t\r]+', ' ', url_title)
                    if url_title:
                        cache.put(url, url_title)

                else:
                    # Read from cache
                    old_url_title = cache.get(url)
                    new_url_title = re.sub(r'[\n\t\r]+', ' ', old_url_title)
                    if old_url_title != new_url_title:
                        cache.put(url, new_url_title)
                    url_title = new_url_title

                if not url_title:
                    url_title = url
                item.url_title = url_title
                item.url = url


class TrelloChecklists:
    def __init__(self, board_json):
        from trello_backup.trello.controller import TrelloObjectParser
        self.all: List[TrelloChecklist] = TrelloObjectParser.parse_trello_checklists(board_json)
        self.by_id: Dict[str, TrelloChecklist] = {c.id: c for c in self.all}


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

    def get_checklist_url_titles(self, cache: WebpageTitleCache):
        for cl in self.checklists:
            cl.get_url_titles(cache)

    def get_extracted_data(self, card_filter_flags: CardFilter, md_formatter: 'MarkdownFormatter'):
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
        plain_text_description = md_formatter.to_plain_text(self.description)
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


class TrelloCards:
    def __init__(self, board_json, trello_lists: TrelloLists, trello_checklists: TrelloChecklists, download_comments=False):
        from trello_backup.trello.controller import TrelloObjectParser
        self.all: List[TrelloCard] = TrelloObjectParser.parse_trello_cards(board_json, trello_lists, trello_checklists, download_comments)
        self.open: List[TrelloCard] = list(filter(lambda c: not c.closed, self.all))


@dataclass
class TrelloBoard:
    id: str
    name: str
    lists: List[TrelloList]

    def __post_init__(self):
        import re
        self.simple_name = re.sub("[ /\ ]+", "-", self.name).lower()

    def get_checklist_url_titles(self, cache: WebpageTitleCache):
        for list in self.lists:
            for card in list.cards:
                card.get_checklist_url_titles(cache)


