from dataclasses import dataclass, field
from typing import List, Dict, Optional, Iterable, Set

from trello_backup.trello.filter import ListFilter


# TODO Revisit this class?
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
    pos: int
    cards: List['TrelloCard'] = field(default_factory=list)

class TrelloLists:
    def __init__(self, board_json, trello_lists_param: Optional[List[TrelloList]] = None):
        from trello_backup.trello.parser import TrelloObjectParser
        self._board_json = board_json
        self._filtered = False

        trello_lists: List[TrelloList] = TrelloObjectParser.parse_trello_lists(board_json)
        self._all_by_id: Dict[str, TrelloList] = {l.id: l for l in trello_lists}

        if trello_lists_param:
            if len(trello_lists_param) < len(trello_lists):
                self._filtered = True
            trello_lists = trello_lists_param
            # Keep object identity consistent: parse_trello_lists() above created a
            # fresh set of TrelloList instances for _all_by_id, but the filtered-in
            # lists live in trello_lists_param. get_by_id() (used to attach cards)
            # reads _all_by_id, while get()/_by_id return the param instances, so
            # without this the cards would be attached to throwaway objects and every
            # filtered list would look empty.
            for l in trello_lists_param:
                self._all_by_id[l.id] = l

        self._by_id: Dict[str, TrelloList] = {l.id: l for l in trello_lists}
        # A board can contain several lists sharing the same name (e.g. archived
        # weekly lists), so name must map to *all* matching lists. Keying a single
        # list per name would silently drop the rest.
        self._by_name: Dict[str, List[TrelloList]] = {}
        for l in trello_lists:
            self._by_name.setdefault(l.name, []).append(l)
        # Filter open trello lists
        self.open: List[TrelloList] = self._sort(filter(lambda tl: not tl.closed, trello_lists))
        self.closed: List[TrelloList] = self._sort(filter(lambda tl: tl.closed, trello_lists))

    def get(self) -> List[TrelloList]:
        # Enumerate by id (always unique), never by name: a board can legitimately
        # contain several lists that share a name (e.g. archived weekly lists), and
        # keying on name would silently collapse them to one entry per name. That
        # previously made cleanup only ever act on a single archived list per name,
        # so duplicate-named archived lists could never be fully removed.
        return self._sort(self._by_id.values())

    def get_ids(self):
        return set(self._by_id.keys())

    def get_all_ids(self):
        return set(self._all_by_id.keys())

    def get_by_id(self, list_id):
        return self._all_by_id[list_id]

    @staticmethod
    def _sort(lists: Iterable[TrelloList]) -> List[TrelloList]:
        return sorted(lists, key=lambda l: l.pos)

    # TODO ASAP filtering Move methods to new class: ListFilterer
    def filter_by_list_names(self, list_names: List[str]) -> 'TrelloLists':
        """
        Retrieves TrelloList objects corresponding to the provided list names.
        Creates a new TrelloLists to only contain the filtered items.
        """
        found: List[TrelloList] = []
        not_found: List[str] = []

        # Iterate through the requested names to check and collect results.
        # Every list matching a name is kept, since names are not unique.
        for name in list_names:
            matches = self._by_name.get(name)
            if matches:
                found.extend(matches)
            else:
                not_found.append(name)

        # Raise an error if any lists were missing
        if not_found:
            missing_names = ', '.join(f"'{n}'" for n in not_found)
            raise ValueError(
                f"The following lists were not found on the board: {missing_names}"
            )
        return TrelloLists(self._board_json, trello_lists_param=self._sort(found))

    # TODO ASAP filtering Move methods to new class: ListFilterer
    def filter_by_list_filter(self, list_filter: ListFilter):
        if list_filter == ListFilter.ALL:
            return TrelloLists(self._board_json, trello_lists_param=list(self.get()))
        elif list_filter == ListFilter.OPEN:
            return TrelloLists(self._board_json, trello_lists_param=list(self.open))
        elif list_filter == ListFilter.CLOSED:
            return TrelloLists(self._board_json, trello_lists_param=list(self.closed))


@dataclass
class TrelloAttachment:
    # TODO ASAP Write testcase and try with test board to see if attachments can be downloaded with url only. If yes, remove api_url parameter
    """
    url (coming directly from attachment JSON): https://trello.com/1/cards/691d029180f5bbd70deb69dc/attachments/691d02d39c6578426ad5fe31/download/Screenshot_2025-11-18_at_6.34.09_PM.png
    api_url (constructed manually): https://api.trello.com/1/cards/691d029180f5bbd70deb69dc/attachments/691d02d39c6578426ad5fe31/download/Screenshot_2025-11-18_at_6.34.09_PM.png
    """
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
    pos: int
    url: str = None
    url_title: str = None

    # TODO ASAP Refactor, this does not belong here
    def get_html(self):
        if self.url:
            if not self.url_title:
                # If title is not found, set title to url
                return f"<a href={self.url}>{self.url}</a>"
            return f"<a href={self.url}>{self.url_title}</a>"
        return self.value


@dataclass
class TrelloChecklist:
    id: str
    name: str
    board_id: str
    card_id: str
    pos: int
    items: List[TrelloChecklistItem]

    def set_url_titles(self, url: str, url_title: str, item: 'TrelloChecklistItem'):
        item.url = url
        item.url_title = url_title


class TrelloChecklists:
    def __init__(self, board_json):
        from trello_backup.trello.parser import TrelloObjectParser
        self._all: List[TrelloChecklist] = TrelloObjectParser.parse_trello_checklists(board_json)
        # self._by_id: Dict[str, TrelloChecklist] = {c.id: c for c in self._all}

    def get_by_ids(self, cl_ids: Set[str]):
        """
        Returns sorted checklists, filtered for ids
        :return:
        """
        return list(filter(lambda cli: cli.id in cl_ids, self._all))


@dataclass
class TrelloCard:
    id: str
    name: str
    short_url: str
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
        return ", ".join(self.labels)


class TrelloCards:
    def __init__(self, board_json, trello_lists: TrelloLists, trello_checklists: TrelloChecklists):
        from trello_backup.trello.parser import TrelloObjectParser
        all, other_lists = TrelloObjectParser.parse_trello_cards(board_json, trello_lists, trello_checklists)
        self.all: List[TrelloCard] = all
        self.cards_for_other_lists: Dict[str, List[TrelloCard]] = other_lists
        self.open: List[TrelloCard] = list(filter(lambda c: not c.closed, self.all))
        self.closed: List[TrelloCard] = list(filter(lambda c: c.closed, self.all))
        self.by_short_url = {c.short_url: c for c in self.all}


@dataclass
class TrelloBoard:
    id: str
    json: str
    name: str
    lists: List[TrelloList]

    def __post_init__(self):
        import re
        self.simple_name = re.sub("[ /\ ]+", "-", self.name).lower()
