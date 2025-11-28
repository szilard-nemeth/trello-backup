import logging
from typing import List, Tuple, Dict

import click
from click import BadOptionUsage

from trello_backup.cli.common import CliCommon
from trello_backup.constants import CTX_HANDLER

LOG = logging.getLogger(__name__)


@click.group()
def backup():
    pass

def get_handler_and_setup_ctx(ctx):
    handler = CliCommon.init_main_cmd_handler(ctx)
    ctx.obj[CTX_HANDLER] = handler
    return handler


@backup.command()
@click.pass_context
@click.argument("board_name")
def board(ctx, board_name: str):
    handler = get_handler_and_setup_ctx(ctx)
    handler.backup_board(board_name)


@backup.command()
@click.pass_context
def boards(ctx):
    handler = get_handler_and_setup_ctx(ctx)
    handler.backup_all_boards()


# TODO ASAP This should be a separate CLI command: 'print board'
@backup.command()
@click.option('-b', '--board', required=True, help='Trello board name')
@click.option('-l', '--list', "list_names",  multiple=True, required=True, help='Trello list name')
# @click.option('-l', '--list', "list_names",  multiple=True, required=True, help='Trello list names to print cards from. Accepts "*" to print cards from all lists.')
@click.pass_context
def cards(ctx, board: str, list_names: Tuple[str]):
    if not list_names:
        raise BadOptionUsage("list_names", "At least one list need to be specified!")

    list_names = list(list_names)
    handler = get_handler_and_setup_ctx(ctx)
    handler.print_cards(board, list_names)
