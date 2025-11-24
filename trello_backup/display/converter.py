from typing import List, Dict, Any

from trello_backup.trello.model import TrelloLists, TrelloBoard, CardFilter, ExtractedCardData


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
            cards = self.filter_cards(list, card_filter_flags)
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

    def filter_cards(self, list, card_filter_flags: CardFilter):
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

    def get_header(self):
        from trello_backup.display.output import TrelloBoardHtmlTableHeader
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
