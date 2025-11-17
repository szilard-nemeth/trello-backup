import json

import requests

ORGANIZATION_ID = "60b31169ff7e174519a40577"

class TrelloUtils:
    auth_query_params = None
    authorization_headers = None
    headers_accept_json = {
        "Accept": "application/json"
    }



class TrelloApi:
    def __init__(self):
        pass

    @classmethod
    def get_board_details(cls, board_id):
        params = {
            "fields": "all",
            "actions": "all",
            "action_fields": "all",
            "actions_limit": 1000,
            "cards": "all",
            "card_fields": "all",
            "card_attachments": "true",
            "labels": "all",
            "lists": "all",
            "list_fields": "all",
            "members": "all",
            "member_fields": "all",
            "checklists": "all",
            "checklist_fields": "all",
            "organization": "false",
        }

        url = "https://api.trello.com/1/boards/{board_id}/".format(board_id=board_id)
        query = dict(TrelloUtils.auth_query_params)
        query.update(params)
        response = requests.request(
            "GET",
            url,
            headers=TrelloUtils.headers_accept_json,
            params=query
        )
        response.raise_for_status()

        parsed_json = json.loads(response.text)

        return parsed_json

    @classmethod
    def get_board_json(cls):
        url = "https://trello.com/b/9GZZWy03/personal-weekly-plan.json"
        response = requests.request(
            "GET",
            url,
            headers=TrelloUtils.headers_accept_json,
            params=TrelloUtils.auth_query_params
        )
        #code = response.status_code
        response.raise_for_status()
        return response

    @classmethod
    def get_lists_of_board(cls):
        url = "https://api.trello.com/1/boards/{id}/lists"

        headers = {
            "Accept": "application/json"
        }

        response = requests.request(
            "GET",
            url,
            headers=headers,
            params=TrelloUtils.auth_query_params
        )

        print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

    @classmethod
    def get_attachment_of_card(cls, card_id: str):
        url = "https://api.trello.com/1/cards/{id}/actions".format(id=card_id)

        headers = {
            "Accept": "application/json"
        }

        response = requests.request(
            "GET",
            url,
            headers=headers,
            params=TrelloUtils.auth_query_params
        )

        # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        parsed_json = json.loads(response.text)
        return parsed_json

    @classmethod
    def create_card(cls):
        url = "https://api.trello.com/1/cards"

        headers = {
            "Accept": "application/json"
        }

        # TODO hardcoded list id
        query = TrelloUtils.auth_query_params.update({'idList': '5abbe4b7ddc1b351ef961414'})
        response = requests.request(
            "POST",
            url,
            headers=headers,
            params=query
        )

        print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

    @classmethod
    def list_boards(cls):
        url = "https://api.trello.com/1/organizations/{org_id}/boards".format(org_id=ORGANIZATION_ID)
        response = requests.request(
            "GET",
            url,
            headers=TrelloUtils.headers_accept_json,
            params=TrelloUtils.auth_query_params
        )

        parsed_json = json.loads(response.text)

        result_dict = {}
        for board in parsed_json:
            b_name = board['name']
            b_id = board['id']
            result_dict[b_name] = b_id

        # TODO debug log
        #print(json.dumps(parsed_json, sort_keys=True, indent=4, separators=(",", ": ")))
        return result_dict

    @classmethod
    def get_actions_for_card(cls, card_id: str):
        url = "https://api.trello.com/1/cards/{id}/actions".format(id=card_id)

        response = requests.request(
            "GET",
            url,
            headers=TrelloUtils.headers_accept_json,
            params=TrelloUtils.auth_query_params
        )

        #print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        parsed_json = json.loads(response.text)
        return parsed_json

    @classmethod
    def get_board_id(cls, board_name):
        # board_resp = get_board()
        # print(json.dumps(json.loads(board_resp.text), sort_keys=True, indent=4, separators=(",", ": ")))
        boards = cls.list_boards()
        available_board_names = list(boards.keys())
        print(f"Available boards: {available_board_names}")
        if board_name not in boards:
            raise KeyError(f"Cannot find board with name: {board_name}")

        board_id = boards[board_name]
        return board_id
