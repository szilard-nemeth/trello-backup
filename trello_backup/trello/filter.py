from enum import Enum, Flag, auto
from typing import List


class CardPropertyFilter(Flag):
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
    ALL = CardPropertyFilter.ALL()
    DESC_AND_CHECKLIST = CardPropertyFilter.WITH_DESCRIPTION | CardPropertyFilter.WITH_CHECKLIST
    DESC_AND_ATTACHMENT = CardPropertyFilter.WITH_DESCRIPTION | CardPropertyFilter.WITH_ATTACHMENT
    CHECKLIST_AND_ATTACHMENT = CardPropertyFilter.WITH_CHECKLIST | CardPropertyFilter.WITH_ATTACHMENT
    ONLY_DESCRIPTION = CardPropertyFilter.WITH_DESCRIPTION



class CardFilterer:
    from trello_backup.trello.model import TrelloList, TrelloCard
    @staticmethod
    def filter_cards(trello_list: TrelloList, card_prop_flags: CardPropertyFilter) -> List[TrelloCard]:
        if CardPropertyFilter.ALL() == card_prop_flags:
            return trello_list.cards

        required_checks = []
        if CardPropertyFilter.WITH_ATTACHMENT in card_prop_flags:
            required_checks.append(lambda card: card.has_attachments)
        if CardPropertyFilter.WITH_DESCRIPTION in card_prop_flags:
            required_checks.append(lambda card: card.has_description)
        if CardPropertyFilter.WITH_CHECKLIST in card_prop_flags:
            required_checks.append(lambda card: card.has_checklist)

        filtered_cards = []
        for card in trello_list.cards:
            # Keep the card if ANY of the required checks pass
            if any(check(card) for check in required_checks):
                filtered_cards.append(card)
            else:
                # Use logging instead of print if possible
                print(f"Not keeping card: {card.name}, filters: {card_filter_flags}")

        return filtered_cards
