import logging
from typing import List, Tuple, Dict

import click
from trello_backup.cli.common import get_handler_and_setup_ctx, webpage_js_titles_cli_option
from trello_backup.cli.context import TrelloCommand

LOG = logging.getLogger(__name__)

# TODO ASAP Add documentation to each command + subcommand
@click.group(help="Interactive cleanup")
def cleanup():
    pass



@cleanup.command(cls=TrelloCommand, help="Interactively cleanup the specified board")
@webpage_js_titles_cli_option(with_negate=False)
@click.option('-l', '--filter-list', "filter_list",  multiple=True, required=False, help='Only cleanup the specified lists')
@click.option('-b', '--batch-mode', is_flag=True, required=False, help='Clean up lists in batch, meaning all cards will be printed and deleted by lists')
@click.pass_context
@click.argument("board_name")
def board(ctx, board_name: str, filter_list: Tuple[str], batch_mode: bool):
    filter_list = list(filter_list)
    handler = get_handler_and_setup_ctx(ctx)
    handler.cleanup_board(board_name, filter_list, batch_mode)
