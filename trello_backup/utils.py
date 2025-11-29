import datetime
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from copy import copy
from os.path import expanduser
from typing import Any

from pythoncommons.constants import ExecutionMode
from pythoncommons.logging_setup import SimpleLoggingSetupConfig, SimpleLoggingSetup, DEFAULT_FORMAT
from pythoncommons.project_utils import ProjectUtils, ProjectRootDeterminationStrategy

from trello_backup.display.console import CliLogger
from trello_backup.constants import PROJECT_NAME

import logging
LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


class DateUtils:
    @staticmethod
    def get_current_datetime(fmt="%Y%m%d_%H%M%f"):
        return DateUtils.now_formatted(fmt)

    @classmethod
    def now(cls):
        return datetime.datetime.now()

    @classmethod
    def now_formatted(cls, fmt):
        return DateUtils.now().strftime(fmt)




class LoggingUtils:
    @staticmethod
    def create_file_handler(log_file_dir, level: int, fname: str):
        log_file_path = os.path.join(log_file_dir, f"{fname}.log")
        fh = TimedRotatingFileHandler(log_file_path, when="midnight")
        fh.suffix = "%Y_%m_%d.log"
        fh.setLevel(level)
        return fh

    @staticmethod
    def configure_file_logging(ctx, level, session_dir):
        root_logger = logging.getLogger()
        handlers = copy(root_logger.handlers)
        file_handler = LoggingUtils.create_file_handler(session_dir, level, fname="trello-session")
        file_handler.formatter = None
        LOG.info("Logging to file: %s", file_handler.baseFilename)
        handlers.append(file_handler)

        fmt = DEFAULT_FORMAT
        if ctx.dry_run:
            fmt = f"[DRY-RUN] {fmt}"
        logging.basicConfig(force=True, format=fmt, level=level, handlers=handlers)

    @staticmethod
    def project_setup(ctx, execution_mode: ExecutionMode = ExecutionMode.PRODUCTION,
                      add_console_handler=False,
                      sanity_check_handlers=False):
        strategy = None
        if execution_mode == ExecutionMode.PRODUCTION:
            strategy = ProjectRootDeterminationStrategy.SYS_PATH
        elif execution_mode == ExecutionMode.TEST:
            strategy = ProjectRootDeterminationStrategy.SYS_PATH
        if not strategy:
            raise ValueError("Unknown project root determination strategy!")
        LOG.info("Project root determination strategy is: %s", strategy)
        ProjectUtils.project_root_determine_strategy = strategy
        ProjectUtils.FORCE_SITE_PACKAGES_IN_PATH_NAME = False
        _ = ProjectUtils.get_output_basedir(PROJECT_NAME, basedir=expanduser("~"))

        fmt = DEFAULT_FORMAT
        if ctx.dry_run:
            fmt = f"[DRY-RUN] {fmt}"
        logging_config: SimpleLoggingSetupConfig = SimpleLoggingSetup.init_logger(
            project_name=PROJECT_NAME,
            logger_name_prefix=PROJECT_NAME,
            execution_mode=ExecutionMode.TEST,
            console_debug=True,
            postfix=None,
            verbose_git_log=True,
            format_str=fmt,
            add_console_handler=add_console_handler,
            sanity_check_number_of_handlers=sanity_check_handlers
        )
        CLI_LOG.info("Logging to files: %s", logging_config.log_file_paths)
        ctx.log_files = list(logging_config.log_file_paths.values())

    @staticmethod
    def remove_console_handler(logger):
        filtered_handlers = list(
            filter(lambda h: isinstance(h, logging.StreamHandler) and h.stream in (sys.stdout, sys.stderr),
                   logger.handlers))

        for handler in filtered_handlers:
            logger.removeHandler(handler)


class ObjectUtils:
    @staticmethod
    def type_check_list_str(val: list[object]):
        '''Determines whether all objects in the list are strings'''
        if not isinstance(val, list):
            raise ValueError()
        for x in val:
            if not isinstance(x, str):
                raise ValueError()
        return val

    @staticmethod
    def type_check_strict_bool(val: Any):
        if val not in ("True", "False", False, True):
            raise ValueError()
        # Convert to bool with dict
        # WARNING: bool("False") returns True, so bool(val) won't work
        string_to_bool = {"true": True, "false": False}
        boolean_value = string_to_bool.get(val.lower())
        return boolean_value

    @staticmethod
    def type_check_strict_str(val: Any):
        if not isinstance(val, str):
            raise ValueError()
        return str(val)

    @staticmethod
    def type_check_lenient_str(val: Any):
        if not isinstance(val, str):
            LOG.warning("Value of '%s' is not an instance of str, converting to str anyway")
        return str(val)

    @staticmethod
    def type_check_date(date_text: str, format="%m/%d/%Y"):
        try:
            datetime.strptime(date_text, format)
        except ValueError:
            raise ValueError("Incorrect date format, should be DD/MM/YYYY")
        return True

    @staticmethod
    def value_check_file_path(path: str):
        if os.path.exists(path):
            return True
        raise ValueError(f"File does not exist: {path}")