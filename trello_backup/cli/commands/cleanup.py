import logging
from typing import List, Tuple, Dict

import click
from trello_backup.cli.common import CliCommon, get_handler_and_setup_ctx
from trello_backup.cli.context import TrelloCommand

LOG = logging.getLogger(__name__)


@click.group()
def cleanup():
    pass



@cleanup.command(cls=TrelloCommand)
@click.option('-l', '--filter-list', "filter_list",  multiple=True, required=False, help='Only cleanup the specified lists')
@click.pass_context
@click.argument("board_name")
def board(ctx, board_name: str, filter_list: Tuple[str]):
    filter_list = list(filter_list)
    handler = get_handler_and_setup_ctx(ctx)
    handler.cleanup_board(board_name, filter_list)
