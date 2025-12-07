import logging
from typing import List, Tuple

import click

from trello_backup.cli.common import get_handler_and_setup_ctx
from trello_backup.cli.context import TrelloCommand

LOG = logging.getLogger(__name__)


@click.group()
def print():
    pass



@print.command(cls=TrelloCommand)
@click.option('-l', '--filter-list', "filter_list",  multiple=True, required=False, help='Only print the specified lists')
@click.pass_context
@click.argument("board_name")
def board(ctx, board_name: str, filter_list: Tuple[str]):
    filter_list = list(filter_list)
    handler = get_handler_and_setup_ctx(ctx)
    handler.print_cards(board_name, filter_list)

@print.command(cls=TrelloCommand)
@click.pass_context
@click.argument("card_links", nargs=-1)
def cards(ctx, card_links: List[str]):
    handler = get_handler_and_setup_ctx(ctx)
    handler.print_cards_by_share_links(list(card_links))
