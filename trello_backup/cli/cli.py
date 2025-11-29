import time

import click
from pythoncommons.constants import ExecutionMode
from pythoncommons.logging_setup import DEFAULT_FORMAT
from rich import print as rich_print, box

from trello_backup.cli.commands.backup import backup
from rich.table import Table

from trello_backup.cli.context import ClickContextWrapper, TrelloGroup
from trello_backup.display.console import CliLogger
from trello_backup.constants import FilePath
from trello_backup.exception import TrelloException
from trello_backup.cli.prompt import TrelloPrompt
from trello_backup.utils import LoggingUtils

import logging
LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


def setup_dirs(ctx: ClickContextWrapper, use_session_dir: bool, add_console_handler: bool = False):
    logs_dir = FilePath.get_logs_dir(use_session_dir)
    if use_session_dir:
        ctx.session_dir = FilePath.get_session_dir()
        ctx.backup_dir = FilePath.get_backups_dir(use_session_dir)

    LoggingUtils.configure_file_logging(ctx, ctx.log_level, logs_dir)
    # TODO: execmode should come from param
    LoggingUtils.project_setup(ctx, execution_mode=ExecutionMode.TEST, add_console_handler=add_console_handler)
    ctx.working_dir = FilePath.get_working_dir()


@click.group(cls=TrelloGroup)
@click.option('--debug/--no-debug', default=False)
@click.option('--dry-run', is_flag=True, default=False)
@click.option('-s', '--session-dir', is_flag=True, default=True, help='Whether to use session dir to save output files.')
@click.pass_context
def cli(ctx: ClickContextWrapper, debug: bool, dry_run: bool = False, session_dir: bool = True):
    if ctx.invoked_subcommand == "usage":
        return

    level = logging.DEBUG if debug else logging.INFO
    fmt = DEFAULT_FORMAT
    if dry_run:
        fmt = f"[DRY-RUN] {fmt}"
    logging.basicConfig(format=fmt, level=level)
    ctx.ensure_object(dict)
    ctx.log_level = level
    ctx.dry_run = dry_run

    LOG.info("Invoked command %s", ctx.invoked_subcommand)
    setup_dirs(ctx, session_dir)
    TrelloPrompt.set_context(ctx)



@cli.command()
@click.option('-n', '--no-wrap', is_flag=True, help='Turns off the wrapping')
def usage(no_wrap: bool = False):
    """
    Prints the aggregated usage of cli
    """
    table = Table(title="Trello CLI", show_lines=True, box=box.SQUARE)
    table.add_column("Command", no_wrap=no_wrap)
    table.add_column("Description", no_wrap=no_wrap)
    table.add_column("Options", no_wrap=no_wrap)

    def recursive_help(cmd, parent=None, is_root: bool = False):
        ctx = click.core.Context(cmd, info_name=cmd.name, parent=parent)
        commands = getattr(cmd, 'commands', {})
        help = list(filter(bool, cmd.get_help(ctx).split("\n")))
        if is_root:
            command = help[0]
            cmd_id = help.index("Commands:")
            desc = "\n".join(help[2:cmd_id])
            options = "\n".join(help[cmd_id + 1:])
        else:
            command = help[0]
            desc = help[1]
            options = "\n".join(help[3:])
            table.add_row(command, desc, options)

        for sub in commands.values():
            recursive_help(sub, ctx)

    recursive_help(cli, is_root=True)
    rich_print(table)



if __name__ == "__main__":
    LOG.info("Started Trello CLI")
    start_time = time.time()
    try:
        cli.add_command(backup)
        cli()
        end_time = time.time()
        LOG.info("Trello CLI execution finished after %d seconds", int(end_time - start_time))
    except TrelloException as e:
        LOG.exception(e)
        # LOG.error(str(e))
        CLI_LOG.print_exception(show_locals=False)
        end_time = time.time()
        LOG.info("Error during execution after %d seconds", int(end_time - start_time))
        exit(1)
