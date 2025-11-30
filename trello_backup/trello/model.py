from dataclasses import dataclass, field
from typing import List, Dict, Optional

from trello_backup.http_server import HTTP_SERVER_PORT
from trello_backup.trello.filter import CardPropertyFilter, CardFilters


# TODO ASAP: Revisit this class?
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
    def __init__(self, board_json, trello_lists_param: Optional[List[TrelloList]] = None):
        from trello_backup.trello.parser import TrelloObjectParser
        self._board_json = board_json
        self._filtered = False

        trello_lists: List[TrelloList] = TrelloObjectParser.parse_trello_lists(board_json)

        if trello_lists_param:
            trello_lists = trello_lists_param
            self._filtered = True

        self.by_id: Dict[str, TrelloList] = {l.id: l for l in trello_lists}
        self.by_name: Dict[str, TrelloList] = {l.name: l for l in trello_lists}
        # Filter open trello lists
        self.open: List[TrelloList] = list(filter(lambda tl: not tl.closed, trello_lists))

    def filter(self, list_names: List[str]) -> 'TrelloLists':
        """
        Retrieves TrelloList objects corresponding to the provided list names.
        Creates a new TrelloLists to only contain the filtered items.
        """
        found: List[TrelloList] = []
        not_found: List[str] = []

        # Iterate through the requested names to check and collect results
        for name in list_names:
            if name in self.by_name:
                found.append(self.by_name[name])
            else:
                not_found.append(name)

        # Raise an error if any lists were missing
        if not_found:
            missing_names = ', '.join(f"'{n}'" for n in not_found)
            raise ValueError(
                f"The following lists were not found on the board: {missing_names}"
            )

        return TrelloLists(self._board_json, trello_lists_param=found)

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
    value: str
    checked: bool
    url: str = None
    url_title: str = None

    def get_html(self):
        if self.url:
            return f"<a href={self.url}>{self.url_title}</a>"
        return self.value


@dataclass
class TrelloChecklist:
    id: str
    name: str
    board_id: str
    card_id: str
    items: List[TrelloChecklistItem]

    def set_url_titles(self, url: str, url_title: str, item: 'TrelloChecklistItem'):
        item.url = url
        item.url_title = url_title


class TrelloChecklists:
    def __init__(self, board_json):
        from trello_backup.trello.parser import TrelloObjectParser
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

    @property
    def open(self):
        return not self.closed

    def get_labels_as_str(self):
        return ",".join(self.labels)


class TrelloCards:
    def __init__(self, board_json, trello_lists: TrelloLists, trello_checklists: TrelloChecklists, download_comments=False):
        from trello_backup.trello.parser import TrelloObjectParser
        self.all: List[TrelloCard] = TrelloObjectParser.parse_trello_cards(board_json, trello_lists, trello_checklists, download_comments)
        self.open: List[TrelloCard] = list(filter(lambda c: not c.closed, self.all))


@dataclass
class TrelloBoard:
    id: str
    json: str
    name: str
    lists: List[TrelloList]

    def __post_init__(self):
        import re
        self.simple_name = re.sub("[ /\ ]+", "-", self.name).lower()
