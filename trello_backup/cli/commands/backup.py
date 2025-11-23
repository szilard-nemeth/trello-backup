import logging
from typing import List, Tuple

import click
from click import BadOptionUsage

from trello_backup.cli.common import CliCommon
from trello_backup.constants import CTX_HANDLER

LOG = logging.getLogger(__name__)


@click.group()
def backup():
    pass


@backup.command()
@click.pass_context
@click.argument("board_name")
def board(ctx, board_name: str):
    handler = CliCommon.init_main_cmd_handler(ctx)
    ctx.obj[CTX_HANDLER] = handler
    handler.backup_board(board_name)


@backup.command()
@click.option('-b', '--board', required=True, help='Trello board name')
@click.option('-l', '--list', "list_names",  multiple=True, required=True, help='Trello list name')
@click.pass_context
def cards(ctx, board: str, list_names: Tuple[str]):
    if not list_names:
        raise BadOptionUsage("list_names", "At least one list need to be specified!")

    list_names = list(list_names)
    handler = CliCommon.init_main_cmd_handler(ctx)
    ctx.obj[CTX_HANDLER] = handler
    handler.print_cards(board, list_names)
