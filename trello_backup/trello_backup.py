import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict
from trello_backup.display.console import CliLogger
from trello_backup.trello.api import TrelloApi
from trello_backup.trello.model import TrelloComment, TrelloList, TrelloAttachment, TrelloChecklistItem, \
    TrelloChecklist, TrelloCard, CardFilter

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

CARD_FILTER_ALL = CardFilter.ALL()
CARD_FILTER_DESC_AND_CHECKLIST = CardFilter.WITH_DESCRIPTION | CardFilter.WITH_CHECKLIST
CARD_FILTER_DESC_AND_ATTACHMENT = CardFilter.WITH_DESCRIPTION | CardFilter.WITH_ATTACHMENT
CARD_FILTER_CHECKLIST_AND_ATTACHMENT = CardFilter.WITH_CHECKLIST | CardFilter.WITH_ATTACHMENT
CARD_FILTER_ONLY_DESC = CardFilter.WITH_DESCRIPTION

ACTIVE_CARD_FILTERS = CARD_FILTER_ALL

