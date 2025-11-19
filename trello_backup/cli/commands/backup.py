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
    handler.backup_board()