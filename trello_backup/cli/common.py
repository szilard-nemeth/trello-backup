import logging
from dataclasses import dataclass
from typing import Iterable


from trello_backup.config_parser.config import ConfigLoader, ConfigReader, TrelloConfig, TrelloCfg
from trello_backup.config_parser.config_validation import ConfigValidator, ValidationContext, ConfigSource
from trello_backup.constants import CTX_DRY_RUN, CTX_LOG_FILES
from trello_backup.exception import TrelloConfigException
from trello_backup.trello.api import TrelloApi

LOG = logging.getLogger(__name__)


class CliCommon:
    @staticmethod
    def init_main_cmd_handler(ctx):
        from trello_backup.cmd_handler import MainCommandHandler

        validator = ConfigValidator()
        validator.set_context(ValidationContext(ConfigSource.MAIN, None))
        config_reader = ConfigReader(validator)
        conf_loader = ConfigLoader(config_reader, validator)
        conf: TrelloConfig = conf_loader.load(ctx)
        context = TrelloContext.create_from_config(ctx, conf, dry_run=ctx.obj[CTX_DRY_RUN])
        handler = MainCommandHandler(context)
        return handler


@dataclass
class TrelloContext:
    config: 'TrelloConfig'
    raise_exc_if_empty = False
    dry_run: bool
    log_files: Iterable[str] = None

    def __post_init__(self):
        LOG.info("Creating context")
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

        log_files = ctx.obj[CTX_LOG_FILES]
        ctx = TrelloContext(conf,
                            dry_run=dry_run,
                            log_files=log_files)
        api_key = conf.get_secret(TrelloCfg.TRELLO_API_KEY)
        token = conf.get_secret(TrelloCfg.TRELLO_TOKEN)
        TrelloApi.init(api_key, token)
        return ctx
