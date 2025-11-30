import logging
from typing import List, Tuple, Dict

import click
from click import BadOptionUsage

from trello_backup.cli.common import CliCommon
from trello_backup.cli.context import TrelloCommand
from trello_backup.display.output import BackupReport

LOG = logging.getLogger(__name__)


@click.group()
def backup():
    pass

def get_handler_and_setup_ctx(ctx):
    handler = CliCommon.init_main_cmd_handler(ctx)
    ctx.handler = handler
    return handler


@backup.command(cls=TrelloCommand)
@click.pass_context
@click.argument("board_name")
def board(ctx, board_name: str):
    handler = get_handler_and_setup_ctx(ctx)
    report = BackupReport()
    handler.backup_board(board_name, report)


@backup.command(cls=TrelloCommand)
@click.pass_context
def boards(ctx):
    handler = get_handler_and_setup_ctx(ctx)
    report = BackupReport()
    handler.backup_all_boards(report)


# TODO ASAP This should be a separate CLI command: 'print board'
# TODO ASAP print all lists by default
# TODO ASAP Add new command: Delete cards with confirmation (one by one or by lists)
@backup.command(cls=TrelloCommand)
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
