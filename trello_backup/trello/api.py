import json
import logging
import os
from pathlib import Path
from typing import Dict

import requests

from trello_backup.constants import FilePath
from trello_backup.display.console import CliLogger
from trello_backup.display.output import OutputHandler
from trello_backup.trello.model import TrelloBoard

TRELLO_API_ROOT = "https://api.trello.com/1/"
CARDS_API = "https://api.trello.com/1/cards"
LIST_BOARDS_API = "https://api.trello.com/1/members/me/boards"
GET_BOARD_DETAILS_API_TMPL = "https://api.trello.com/1/boards/{id}/"
GET_BOARD_LISTS_API_TMPL = "https://api.trello.com/1/boards/{id}/lists"
GET_CARD_ACTIONS_API_TMPL = "https://api.trello.com/1/cards/{id}/actions"

# TODO ASAP need to move to config file
ORGANIZATION_ID = "60b31169ff7e174519a40577"
LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


from abc import ABC, abstractmethod
from typing import Dict, Any

class AbstractTrelloApi(ABC):
    @abstractmethod
    def list_boards(self) -> Dict[str, str]:
        """Returns board name to board ID mapping."""
        pass

    @abstractmethod
    def get_board_id(self, name: str) -> str:
        """Returns the ID for a given board name."""
        pass

    @abstractmethod
    def get_board_details(self, board_id: str) -> Dict[str, Any]:
        """Returns the raw JSON data for a specific board."""
        pass

    @abstractmethod
    def download_attachments(self, board):
        pass


class TrelloApi(AbstractTrelloApi):
    auth_query_params = None
    authorization_headers = None
    headers_accept_json = {
        "Accept": "application/json"
    }

    def __init__(self):
        pass

    @classmethod
    def init(cls, api_key, token):
        TrelloApi.auth_query_params = {
            'key': api_key,
            'token': token
        }
        TrelloApi.authorization_headers = {
            "Authorization": "OAuth oauth_consumer_key=\"{}\", oauth_token=\"{}\"".format(api_key, token)
        }

    @classmethod
    def list_boards(cls):
        """
        Gets all boards associated with the API token's user.
        https://developer.atlassian.com/cloud/trello/rest/api-group-members/#api-members-id-boards-get
        """
        params = {
            "filter": "all",  # Return all board types (open, closed, pinned, etc.)
            "fields": "id,name"  # Only request the ID and name fields for efficiency
        }

        query = dict(TrelloApi.auth_query_params)
        query.update(params)

        response = requests.request(
            "GET",
            LIST_BOARDS_API,
            headers=TrelloApi.headers_accept_json,
            params=query
        )
        response.raise_for_status()

        # The response is a list of board objects
        parsed_json = json.loads(response.text)

        result_dict = {}
        for board in parsed_json:
            b_name = board.get('name')
            b_id = board.get('id')
            if b_name and b_id:
                result_dict[b_name] = b_id

        return result_dict

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

        query = dict(TrelloApi.auth_query_params)
        query.update(params)
        response = requests.request(
            "GET",
            GET_BOARD_DETAILS_API_TMPL.format(id=board_id),
            headers=TrelloApi.headers_accept_json,
            params=query
        )
        response.raise_for_status()

        parsed_json = json.loads(response.text)

        return parsed_json

    @classmethod
    def get_board_json(cls, board_name):
        url = f"https://trello.com/b/9GZZWy03/{board_name}.json"
        response = requests.request(
            "GET",
            url,
            headers=TrelloApi.headers_accept_json,
            params=TrelloApi.auth_query_params
        )
        #code = response.status_code
        response.raise_for_status()
        return response

    @classmethod
    def get_lists_of_board(cls, board_id: str):
        headers = {
            "Accept": "application/json"
        }

        response = requests.request(
            "GET",
            GET_BOARD_LISTS_API_TMPL.format(id=board_id),
            headers=headers,
            params=TrelloApi.auth_query_params
        )

    @classmethod
    def get_attachment_of_card(cls, card_id: str):
        headers = {
            "Accept": "application/json"
        }

        response = requests.request(
            "GET",
            GET_CARD_ACTIONS_API_TMPL.format(id=card_id),
            headers=headers,
            params=TrelloApi.auth_query_params
        )

        parsed_json = json.loads(response.text)
        return parsed_json

    @classmethod
    def create_card(cls, list_id):
        headers = {
            "Accept": "application/json"
        }

        # list_id_example: 5abbe4b7ddc1b351ef961414
        query = TrelloApi.auth_query_params.update({'idList': list_id})
        response = requests.request(
            "POST",
            CARDS_API,
            headers=headers,
            params=query
        )

    @classmethod
    def get_actions_for_card(cls, card_id: str):
        response = requests.request(
            "GET",
            GET_CARD_ACTIONS_API_TMPL.format(id=card_id),
            headers=TrelloApi.headers_accept_json,
            params=TrelloApi.auth_query_params
        )

        parsed_json = json.loads(response.text)
        return parsed_json

    @classmethod
    def get_board_id(cls, board_name: str):
        boards: Dict[str, str] = cls.list_boards()
        available_board_names = list(boards.keys())
        CLI_LOG.info(f"Available boards: {available_board_names}")
        if board_name not in boards:
            raise KeyError(f"Cannot find board with name: {board_name}")

        board_id = boards[board_name]
        return board_id

    # TODO ASAP Refactor this does not belong here
    @classmethod
    def download_attachments(cls, board):
        for list in board.lists:
            for card in list.cards:
                for attachment in card.attachments:
                    if attachment.is_upload:
                        fpath = TrelloApi.download_and_save_attachment(attachment)
                        attachment.downloaded_file_path = "file://" + fpath

    # TODO ASAP Refactor this does not belong here
    @classmethod
    def download_and_save_attachment(cls, attachment):
        """
        Handles file path generation and persistence of the stream.
        """
        file_path = os.path.join(
            FilePath.OUTPUT_DIR_ATTACHMENTS,
            f"{attachment.id}-{attachment.file_name}"
        )

        with open(file_path, 'wb') as out_file:
            # 2. Get the stream/chunks (Networking logic)
            for chunk in cls._get_attachment_chunks(attachment):
                out_file.write(chunk)
        return file_path


    @classmethod
    def _get_attachment_stream(cls, attachment):
        """
        Initiates the request and returns the raw response stream object.
        Caller is responsible for closing the stream.
        """
        response = requests.request(
            "GET",
            attachment.api_url,
            headers=TrelloApi.authorization_headers,
            stream=True # Crucial: ensures the entire file isn't loaded into memory
        )
        # This still belongs here, as it validates the success of the network request
        response.raise_for_status()

        # We return the response object itself, but the caller must handle
        # the response's context manager or call response.close()
        return response

    @classmethod
    def _get_attachment_chunks(cls, attachment):
        """
        Initiates the request and yields data chunks, ensuring the connection is closed.
        """
        with requests.request(
                "GET",
                attachment.api_url,
                headers=TrelloApi.authorization_headers,
                stream=True
        ) as response:
            response.raise_for_status()
            # Decode content handles things like gzip compression
            response.raw.decode_content = True

            # Iterating over the response ensures data is streamed
            for chunk in response.iter_content(chunk_size=1024 * 1024): # 1MB chunks
                if chunk:  # filter out keep-alive chunks
                    yield chunk

    @staticmethod
    def reformat_attachment_url(card_id, attachment_id, attachment_filename):
        # Convert URLs as Trello attachments cannot be downloaded from trello.com URL anymore..
        # See details here: https://community.developer.atlassian.com/t/update-authenticated-access-to-s3/43681
        # Example URL: https://api.trello.com/1/cards/{idCard}/attachments/{idAttachment}/download/{attachmentFileName}
        # Source: https://trello.com/1/cards/60d8951d65e3c9345794d20a/attachments/631332fc6b78cf0135be0a37/download/image.png
        # Target: https://api.trello.com/1/cards/60d8951d65e3c9345794d20a/attachments/631332fc6b78cf0135be0a37/download/image.png
        return f"{CARDS_API}/{card_id}/attachments/{attachment_id}/download/{attachment_filename}"


class OfflineTrelloApi(AbstractTrelloApi):
    API_ENDPOINT_TO_FILE = {LIST_BOARDS_API: "list_boards.json",
                            GET_BOARD_DETAILS_API_TMPL: "board-cloudera.json"}
    TESTS_DIR = FilePath.get_dir_from_root("tests", parent_dir=FilePath.REPO_ROOT_DIRNAME)
    RESOURCES_DIR = FilePath.get_dir_from_root("resources", parent_dir=TESTS_DIR)

    @staticmethod
    def _load_resource_file(filename) -> str:
        file_path = os.path.join(OfflineTrelloApi.RESOURCES_DIR, filename)
        contents = Path(file_path).read_text()
        return contents

    def __init__(self):
        pass

    def list_boards(self) -> Dict[str, str]:
        """
        Returns board mappings.
        Key: Board name
        Value: Board id
        :return:
        """
        boards_list = self._load_boards_json()
        return self._get_boards_by_name(boards_list)

    def get_board_id(self, name: str) -> str:
        boards_list = self._load_boards_json()
        boards_by_name = self._get_boards_by_name(boards_list)
        return boards_by_name.get(name)

    def get_board_details(self, board_id: str) -> Dict[str, Any]:
        boards_list = self._load_boards_json()
        boards_by_id = self._get_boards_by_id(boards_list)
        board_name = boards_by_id[board_id]

        # Create TrelloBoard object to get short filename
        tmp_board_obj = TrelloBoard("dummy_id", "no_json", board_name, [])
        board_file_name = OutputHandler.get_board_filename_by_board(tmp_board_obj)

        # Read raw board JSON from a local file based on board_id
        board_json = OfflineTrelloApi._load_resource_file(board_file_name)
        return json.loads(board_json)

    @staticmethod
    def _load_boards_json() -> Any:
        list_boards_json = OfflineTrelloApi._load_resource_file("list_boards.json")
        return json.loads(list_boards_json)

    @staticmethod
    def _get_boards_by_name(boards_list):
        d = {}
        for b in boards_list:
            d[b["name"]] = b["id"]
        return d

    @staticmethod
    def _get_boards_by_id(boards_list):
        d = {}
        for b in boards_list:
            d[b["id"]] = b["name"]
        return d

    def download_attachments(self, board):
        # intentionally empty
        pass


class NetworkStatusService:
    def __init__(self, ctx):
        self._online = not ctx.offline

    def is_online(self):
        return self._online


class TrelloRepository:
    def __init__(self,
                 online_api: TrelloApi,
                 offline_api: OfflineTrelloApi,
                 network_service: NetworkStatusService):
        self._online = online_api
        self._offline = offline_api
        self._network = network_service

    def get_api(self) -> AbstractTrelloApi:
        # Simple selection logic
        if self._network.is_online():
            return self._online
        else:
            return self._offline