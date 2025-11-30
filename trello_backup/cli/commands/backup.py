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
    return handler.backup_board(board_name, report)


@backup.command(cls=TrelloCommand)
@click.pass_context
def boards(ctx):
    handler = get_handler_and_setup_ctx(ctx)
    report = BackupReport()
    return handler.backup_all_boards(report)
