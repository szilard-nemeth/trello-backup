from typing import List

from trello_backup.trello.model import TrelloList, CardFilter, TrelloCard


class CardFilterer:
    @staticmethod
    def filter_cards(trello_list: TrelloList, card_filter_flags: CardFilter) -> List[TrelloCard]:
        if CardFilter.ALL() == card_filter_flags:
            return trello_list.cards

        with_attachment = CardFilter.WITH_ATTACHMENT in card_filter_flags
        with_description = CardFilter.WITH_DESCRIPTION in card_filter_flags
        with_checklist = CardFilter.WITH_CHECKLIST in card_filter_flags

        filtered_cards = []
        for card in trello_list.cards:
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