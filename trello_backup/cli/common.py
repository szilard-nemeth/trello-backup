import logging
from dataclasses import dataclass
from typing import Iterable

from trello_backup.config_parser.config import ConfigLoader, ConfigReader, TrelloConfig, TrelloCfg
from trello_backup.config_parser.config_validation import ConfigValidator, ValidationContext, ConfigSource
from trello_backup.constants import FilePath
from trello_backup.display.output import OutputHandlerFactory, MarkdownFormatter, TrelloDataConverter
from trello_backup.exception import TrelloConfigException
from trello_backup.http_server import HttpServer, HTTP_SERVER_PORT
from trello_backup.trello.api import TrelloApi, TrelloRepository, OfflineTrelloApi, NetworkStatusService
from trello_backup.trello.cache import WebpageTitleCache
from trello_backup.trello.service import TrelloOperations, TrelloTitleService

LOG = logging.getLogger(__name__)

def get_handler_and_setup_ctx(ctx):
    handler = CliCommon.init_main_cmd_handler(ctx)
    ctx.handler = handler
    return handler


class CliCommon:
    @staticmethod
    def init_main_cmd_handler(ctx):
        from trello_backup.cmd_handler import MainCommandHandler

        validator = ConfigValidator()
        validator.set_context(ValidationContext(ConfigSource.MAIN, None))
        config_reader = ConfigReader(validator)
        conf_loader = ConfigLoader(config_reader, validator)
        conf: TrelloConfig = conf_loader.load(ctx)
        context = TrelloContext.create_from_config(ctx, conf, dry_run=ctx.dry_run)

        # Initialize WebpageTitleCache so 'board.get_checklist_url_titles' can use it
        cache = WebpageTitleCache()
        webpage_title_service = TrelloTitleService(cache)
        md_formatter = MarkdownFormatter()
        data_converter = TrelloDataConverter(md_formatter, HTTP_SERVER_PORT)

        # Serve attachment files with http server
        if context.config.get(TrelloCfg.SERVE_ATTACHMENTS):
            http_server = HttpServer(FilePath.OUTPUT_DIR_ATTACHMENTS)
            http_server.launch()

        network_status_service = NetworkStatusService(ctx)
        trello_repository = TrelloRepository(TrelloApi(), OfflineTrelloApi(), network_status_service)
        trello_ops = TrelloOperations(trello_repository, cache, webpage_title_service, data_converter)
        handler = MainCommandHandler(context, trello_ops, data_converter, OutputHandlerFactory)
        return handler


class TrelloContext:
    def __init__(self, config, backup_dir, dry_run, log_files):
        LOG.info(f"Creating {TrelloContext.__name__}")
        self.raise_exc_if_empty = False

        self.config: 'TrelloConfig' = config
        self.backup_dir = backup_dir
        self.dry_run: bool = dry_run
        self.log_files: Iterable[str] = log_files
        if not self.config:
            if self.raise_exc_if_empty:
                raise TrelloConfigException("Config not defined for TrelloContext")
            return


    @classmethod
    def create_from_config(cls, ctx, conf, dry_run=False):
        if dry_run:
            LOG.info("Using dry-run mode for initializing context")
        else:
            LOG.info("Using normal mode for initializing context")

        ctx = TrelloContext(conf,
                            ctx.backup_dir,
                            dry_run=dry_run,
                            log_files=ctx.log_files)
        api_key = conf.get_secret(TrelloCfg.TRELLO_API_KEY)
        token = conf.get_secret(TrelloCfg.TRELLO_TOKEN)
        TrelloApi.init(api_key, token)
        return ctx