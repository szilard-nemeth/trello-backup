import logging
from typing import List, Tuple, Dict

import click
from click import BadOptionUsage

from trello_backup.cli.common import CliCommon, get_handler_and_setup_ctx
from trello_backup.cli.context import TrelloCommand
from trello_backup.display.output import BackupReport

LOG = logging.getLogger(__name__)


@click.group()
def print():
    pass



# TODO ASAP cli Add new command: Delete cards with confirmation (one by one or by lists)
@print.command(cls=TrelloCommand)
@click.option('-l', '--filter-list', "filter_list",  multiple=True, required=False, help='Only print the specified lists')
@click.pass_context
@click.argument("board_name")
def board(ctx, board_name: str, filter_list: Tuple[str]):
    filter_list = list(filter_list)
    handler = get_handler_and_setup_ctx(ctx)
    handler.print_cards(board_name, filter_list)
