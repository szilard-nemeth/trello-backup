import logging
import os.path
import re
import unittest
import urllib
from pathlib import Path
from string import Template
from typing import Dict

import pytest
from httpretty import httpretty
from pythoncommons.url_utils import UrlUtils

from tests.conftest import PyTestCliRunner
from trello_backup.cli.cli import setup_dirs
from trello_backup.cli.commands.backup import backup
from trello_backup.cli.context import ClickContextWrapper
from trello_backup.constants import FilePath
from trello_backup.display.output import OutputType
from trello_backup.trello.api import LIST_BOARDS_API, GET_BOARD_DETAILS_API_TMPL, CARDS_API, GET_CARD_ACTIONS_API_TMPL

LOG = logging.getLogger(__name__)

USE_REAL_API = False
CLI_ENTRY_POINT_BACKUP = backup
COMMAND_BACKUP = "backup"
SUBCOMMAND_BOARD = "board"
BOARD_ID_CLOUDERA = "616ec99dc34d9d608dc5502b"
API_ENDPOINT_TO_FILE = {LIST_BOARDS_API: "list_boards.json",
                        GET_BOARD_DETAILS_API_TMPL: "board-cloudera.json",
                        }
MOCKED_ATTACHMENT_URLS = ["https://api.trello.com/1/cards/691d029180f5bbd70deb69dc/attachments/691d02d39c6578426ad5fe31/download/Screenshot_2025-11-18_at_6.34.09_PM.png",
]

CARD_ACTION_RESPONSE_TEMPLATE = Template("""
[ {
  "id" : "64516323ab2a3046a47ff39b",
  "idMemberCreator" : "57213e43028b63d18cd5b9f2",
  "data" : {
    "card" : {
      "idList" : "$list_id",
      "id" : "$card_id",
      "name" : "DEX filter for open tasks assigned to me",
      "idShort" : 1201,
      "shortLink" : "arsWJv53"
    },
    "board" : {
      "id" : "616ec99dc34d9d608dc5502b",
      "name" : "CLOUDERA: Weekly Plan",
      "shortLink" : "AZCBY076"
    }
  },
  "type" : "updateCard",
  "date" : "2023-05-02T19:23:15.431Z",
  "memberCreator" : {
    "id" : "<omitted>",
    "fullName" : "nemethszyszy",
    "username" : "szilard_nemeth"
  }
} ]""")

# Define the minimum size in bytes (10 KB = 10 * 1024 bytes)
MIN_FILE_SIZE_KB = 10
MIN_FILE_SIZE_BYTES = MIN_FILE_SIZE_KB * 1024

class UrlHelper:
    @staticmethod
    def extract_trello_attachment_info_regex(url_string):
        """
        Extracts the card ID, attachment ID, and filename from a Trello attachment URL
        using a regular expression, avoiding hardcoded indexes.

        Args:
            url_string (str): The Trello attachment download URL.

        Returns:
            dict: A dictionary containing the extracted information.
        """
        # 1. Parse the URL to get the path
        parsed_url = urllib.parse.urlparse(url_string)
        path = parsed_url.path

        # 2. Define the regex pattern to capture the three parts
        # The pattern matches the fixed parts and uses capture groups '()' for the variable parts.
        regex_pattern = r'^/1/cards/([^/]+)/attachments/([^/]+)/download/(.*)$'

        # 3. Apply the regex to the path
        match = re.match(regex_pattern, path)

        if match:
            # 4. Extract captured groups
            card_id = match.group(1)
            attachment_id = match.group(2)
            # 5. Unquote the filename to handle URL encoding (e.g., spaces as %20)
            filename = urllib.parse.unquote(match.group(3))

            # 6. Return the data in the preferred dictionary format
            return {
                "card_id": card_id,
                "attachment_id": attachment_id,
                "file_name": filename
            }
        else:
            # Handle cases where the URL structure might be unexpected
            return {
                "error": "URL structure does not match the Trello attachment download pattern.",
                "url_path": path
            }


class TestTrelloApiIntegration(unittest.TestCase):
    TESTS_DIR = FilePath.get_dir_from_root("tests", parent_dir=FilePath.REPO_ROOT_DIRNAME)
    RESOURCES_DIR = FilePath.get_dir_from_root("resources", parent_dir=TESTS_DIR)

    def setUp(self):
        if not USE_REAL_API:
            # enable HTTPretty so that it will monkey patch the socket module
            httpretty.enable()

    def tearDown(self) -> None:
        if not USE_REAL_API:
            # disable afterwards, so that you will have no problems in code that uses that socket module
            httpretty.disable()
            # reset HTTPretty state (clean up registered urls and request history)
            httpretty.reset()

    @pytest.fixture(autouse=True)
    def runner(self, click_runner: PyTestCliRunner):
        print("Exec capfd")
        self.runner: PyTestCliRunner = click_runner

    @staticmethod
    def _mock_api_endpoint(endpoint: str,
                           template_params: Dict[str, str],
                           match_querystring=False,
                           override_json=None):
        url = endpoint
        url = url.format(**template_params)
        response = override_json
        if not override_json:
            response = TestTrelloApiIntegration._load_resource_file_for_api_endpoint(endpoint)

        # final_url = rf"{url}.*"
        final_url = UrlUtils.sanitize_url(url)

        if ".*" in final_url:
            final_url = re.compile(final_url)
        LOG.info("Mocked URL: %s", final_url)
        httpretty.register_uri(
            httpretty.GET,
            final_url,
            body=response,
            match_querystring=match_querystring
        )
        return final_url

    def _mock_api_endpoint_for_card_attachment(self, card_id: str, attachment_id: str, attachment_filename: str):
        # api_url, see: reformat_attachment_url
        # file_path, see: download_and_save_attachment
        api_url = f"{CARDS_API}/{card_id}/attachments/{attachment_id}/download/{attachment_filename}"
        file_name = f"{attachment_id}-{attachment_filename}"
        file_path = os.path.join(TestTrelloApiIntegration.RESOURCES_DIR, "attachments", file_name)
        self._mock_api_endpoint_custom(api_url, file_path)

    def _mock_api_endpoint_custom(self, endpoint: str, file_path: str):
        url = endpoint
        response = self._load_resource_file_custom(file_path)
        final_url = UrlUtils.sanitize_url(url)
        LOG.info("Mocked URL: %s", final_url)
        httpretty.register_uri(
            httpretty.GET,
            final_url,
            body=response,
            match_querystring=False
        )
        return final_url

    @staticmethod
    def _load_resource_file_for_api_endpoint(endpoint) -> str:
        filename = API_ENDPOINT_TO_FILE[endpoint]
        file_path = os.path.join(TestTrelloApiIntegration.RESOURCES_DIR, filename)
        contents = Path(file_path).read_text()
        return contents

    @staticmethod
    def _load_resource_file_custom(file_path: str) -> str:
        contents = Path(file_path).read_text()
        return contents

    @staticmethod
    def _create_context_obj(offline=False):
        # Hack to set context_class on click.Group
        CLI_ENTRY_POINT_BACKUP.context_class = ClickContextWrapper

        tmp_ctx = CLI_ENTRY_POINT_BACKUP.make_context(COMMAND_BACKUP, args=[SUBCOMMAND_BOARD])
        tmp_ctx.ensure_object(dict)
        tmp_ctx.log_level = logging.DEBUG
        tmp_ctx.dry_run = False
        tmp_ctx.offline = offline
        setup_dirs(tmp_ctx, use_session_dir=True, add_console_handler=True)
        return tmp_ctx.obj

    def test_backup_board_cloudera(self):
        _ = self._mock_api_endpoint(LIST_BOARDS_API, {})
        _ = self._mock_api_endpoint(GET_BOARD_DETAILS_API_TMPL, {"id": BOARD_ID_CLOUDERA})
        # TODO ASAP Do not return for all cards, only Nth card: https://gemini.google.com/app/211f0036bb2c99a2
        _ = self._mock_api_endpoint(GET_CARD_ACTIONS_API_TMPL, {"id": ".*"},
                                    override_json=CARD_ACTION_RESPONSE_TEMPLATE.substitute(list_id="1", card_id="2"))

        for url in MOCKED_ATTACHMENT_URLS:
            d = UrlHelper.extract_trello_attachment_info_regex(url)
            self._mock_api_endpoint_for_card_attachment(d["card_id"], d["attachment_id"], d["file_name"])
        obj = self._create_context_obj()

        # In case pytest is the runner, please refer to https://github.com/pallets/click/issues/824#issuecomment-1583293065
        result = self.runner.invoke(
            CLI_ENTRY_POINT_BACKUP, f"{SUBCOMMAND_BOARD} Cloudera".split(),
            standalone_mode=False, obj=obj)
        if result.exc_info:
            LOG.exception("Error while invoking command", exc_info=result.exc_info)
            self.fail()
        self.assertEqual(0, result.exit_code, result.output)

        report = result.return_value
        self.assertIsNotNone(report)
        expected_result_types = [OutputType.HTML_FILE, OutputType.CUSTOM_HTML_TABLE, OutputType.RICH_HTML_TABLE, OutputType.BOARD_JSON, OutputType.CSV]
        for rt in expected_result_types:
            files = report.get_files(rt)
            self.assertTrue(len(files) > 0)
            for f in files:
                self.assertTrue(os.path.exists(f), f"File does not exist: {f}")
                size_bytes = os.path.getsize(f)
                self.assertTrue(size_bytes > MIN_FILE_SIZE_BYTES, f"File '{f}' is less than {MIN_FILE_SIZE_KB} KBs")

    def test_backup_board_cloudera_offline(self):
        obj = self._create_context_obj(offline=True)

        result = self.runner.invoke(
            CLI_ENTRY_POINT_BACKUP, f"{SUBCOMMAND_BOARD} Cloudera".split(),
            standalone_mode=False, obj=obj)
        if result.exc_info:
            LOG.exception("Error while invoking command", exc_info=result.exc_info)
            self.fail()
        self.assertEqual(0, result.exit_code, result.output)

        report = result.return_value
        self.assertIsNotNone(report)
        expected_result_types = [OutputType.HTML_FILE, OutputType.CUSTOM_HTML_TABLE, OutputType.RICH_HTML_TABLE, OutputType.BOARD_JSON, OutputType.CSV]
        for rt in expected_result_types:
            files = report.get_files(rt)
            self.assertTrue(len(files) > 0)
            for f in files:
                self.assertTrue(os.path.exists(f), f"File does not exist: {f}")
                size_bytes = os.path.getsize(f)
                self.assertTrue(size_bytes > MIN_FILE_SIZE_BYTES, f"File '{f}' is less than {MIN_FILE_SIZE_KB} KBs")