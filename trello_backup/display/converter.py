from typing import List, Dict, Any

from trello_backup.display.output import MarkdownFormatter
from trello_backup.http_server import HTTP_SERVER_PORT


class TrelloDataConverter:
    @staticmethod
    def convert_to_output_data(trello_lists) -> List[Dict[str, Any]]:
        md_formatter = MarkdownFormatter()

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
                    # "description": md_formatter.to_plain_text(card.description),
                    "description": md_formatter.to_plain_text(card.description),
                    "attachments": [
                        {
                            "name": a.name,
                            "url": a.url,
                            "local_path": a.downloaded_file_path,
                            "local_server_path": f"http://localhost:{HTTP_SERVER_PORT}/{a.downloaded_file_path.split('/')[-1]}" if a.downloaded_file_path else ""
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
