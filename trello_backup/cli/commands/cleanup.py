import logging
from typing import List, Tuple, Dict

import click
from trello_backup.cli.common import CliCommon, get_handler_and_setup_ctx
from trello_backup.cli.context import TrelloCommand

LOG = logging.getLogger(__name__)

# TODO ASAP Add documentation to each command + subcommand
@click.group(help="Interactive cleanup")
def cleanup():
    pass



@cleanup.command(cls=TrelloCommand, help="Interactively cleanup the specified board")
@click.option('-l', '--filter-list', "filter_list",  multiple=True, required=False, help='Only cleanup the specified lists')
@click.option('-b', '--batch-mode', is_flag=True, required=False, help='Clean up lists in batch, meaning all cards will be printed and deleted by lists')
@click.option('-a', '--cleanup-archived-lists', is_flag=True, required=False, help='Permanently removes all empty archived lists on the board (moves them to a throwaway board that is then deleted). Non-empty archived lists are skipped. Not combinable with --filter-list.')
@click.pass_context
@click.argument("board_name")
def board(ctx, board_name: str, filter_list: Tuple[str], batch_mode: bool, cleanup_archived_lists: bool):
    filter_list = list(filter_list)
    handler = get_handler_and_setup_ctx(ctx)
    handler.cleanup_board(board_name, filter_list, batch_mode, cleanup_archived_lists)
