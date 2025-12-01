import logging
from enum import Enum, Flag, auto
from typing import List, Callable, Any, Dict
from trello_backup.exception import TrelloException


LOG = logging.getLogger(__name__)

class CardPropertyFilter(Flag):
    NONE = 0
    OPEN = auto()
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
    ALL = CardPropertyFilter.ALL()
    OPEN = CardPropertyFilter.OPEN
    DESC_AND_CHECKLIST = CardPropertyFilter.WITH_DESCRIPTION | CardPropertyFilter.WITH_CHECKLIST
    DESC_AND_ATTACHMENT = CardPropertyFilter.WITH_DESCRIPTION | CardPropertyFilter.WITH_ATTACHMENT
    CHECKLIST_AND_ATTACHMENT = CardPropertyFilter.WITH_CHECKLIST | CardPropertyFilter.WITH_ATTACHMENT
    ONLY_DESCRIPTION = CardPropertyFilter.WITH_DESCRIPTION


class ListFilter(Enum):
    ALL = "all"
    OPEN = "open"



class CardFilterer:
    @staticmethod
    def filter_cards(trello_list: 'TrelloList', card_filters: CardFilters) -> List['TrelloCard']:
        from trello_backup.trello.model import TrelloCard
        card_prop_flags = card_filters.value
        if CardPropertyFilter.ALL() == card_prop_flags:
            return trello_list.cards

        all_checks: Dict[CardPropertyFilter, Callable[['TrelloCard'], Any]] = {
            CardPropertyFilter.WITH_ATTACHMENT: lambda card: card.has_attachments,
            CardPropertyFilter.WITH_DESCRIPTION: lambda card: card.has_description,
            CardPropertyFilter.WITH_CHECKLIST: lambda card: card.has_checklist,
            CardPropertyFilter.OPEN: lambda card: card.open
        }


        required_checks: Dict[CardPropertyFilter, Callable[['TrelloCard'], Any]] = {}
        filters = [CardPropertyFilter.WITH_ATTACHMENT, CardPropertyFilter.WITH_DESCRIPTION, CardPropertyFilter.WITH_CHECKLIST, CardPropertyFilter.OPEN]
        for filter in filters:
            required_checks[filter] = all_checks[filter]

        all_filters = set([f for f in CardPropertyFilter])
        defined_filters = set(filters)
        missing = all_filters.difference(defined_filters)
        if missing:
            raise TrelloException(f"Found undefined card checker for filters: {missing}")

        filtered_cards = []
        for card in trello_list.cards:
            # Keep the card if ANY of the required checks pass
            if any(check(card) for check in required_checks.values()):
                filtered_cards.append(card)
            else:
                LOG.debug(f"Discarding card: {card.name}, filters: {card_prop_flags}")

        return filtered_cards
