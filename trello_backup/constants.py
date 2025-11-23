import logging
import os.path
import os
from enum import Enum

from pythoncommons.file_utils import FileUtils, FindResultType
from pythoncommons.project_utils import SimpleProjectUtils


LOG = logging.getLogger(__name__)
PROJECT_NAME = "trello-backup"


class FilePath:
    REPO_ROOT_DIRNAME = "trello-backup"
    MODULE_ROOT_NAME = "trello_backup"
    REPO_ROOT_DIR = FileUtils.find_repo_root_dir(__file__, REPO_ROOT_DIRNAME)
    TRELLO_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "trello-backup-output")
    OUTPUT_DIR_ATTACHMENTS = os.path.join(TRELLO_OUTPUT_DIR, "attachments")
    TRELLO_BACKUP_DIR = SimpleProjectUtils.get_project_dir(
        basedir=REPO_ROOT_DIR,
        parent_dir=REPO_ROOT_DIRNAME,
        dir_to_find=MODULE_ROOT_NAME,
        find_result_type=FindResultType.DIRS,
        exclude_dirs=[],
    )
    WEBPAGE_TITLE_CACHE_FILE = FileUtils.join_path(TRELLO_OUTPUT_DIR, 'webpage_title_cache')
    FileUtils.ensure_dir_created(TRELLO_OUTPUT_DIR)
    FileUtils.ensure_dir_created(OUTPUT_DIR_ATTACHMENTS)

    @classmethod
    def get_file_from_root(cls, fname):
        return SimpleProjectUtils.get_project_file(basedir=FilePath.REPO_ROOT_DIR,
                                                   file_to_find=fname,
                                                   find_result_type=FindResultType.FILES)

    @classmethod
    def get_file_from_basedir(cls, fname, basedir):
        return SimpleProjectUtils.get_project_file(basedir=basedir,
                                                   file_to_find=fname,
                                                   find_result_type=FindResultType.FILES)

    @classmethod
    def get_dir_from_root(cls, dirname, parent_dir, excludes=None, exact_dirname_match=False):
        kwargs = {"basedir": FilePath.REPO_ROOT_DIR,
                  "dir_to_find": dirname,
                  "find_result_type": FindResultType.DIRS,
                  "exact_dirname_match": exact_dirname_match
                  }
        if parent_dir:
            kwargs["parent_dir"] = os.path.basename(parent_dir)
        if excludes:
            kwargs["exclude_dirs"] = excludes
        return SimpleProjectUtils.get_project_dir(**kwargs)

    @classmethod
    def get_file_path_from_root(cls, fname):
        return os.path.join(FilePath.REPO_ROOT_DIR, fname)

    @classmethod
    def get_logs_dir(cls):
        return cls._get_child_dir(FilePath.TRELLO_OUTPUT_DIR, "logs")

    @classmethod
    def _get_child_dir(cls, parent, child, create=False):
        logs_dir = os.path.join(parent, child)
        if not os.path.exists(logs_dir) and create:
            os.makedirs(logs_dir)
        return logs_dir

    @classmethod
    def get_working_dir(cls):
        return os.getcwd()

    @classmethod
    def get_session_dir(cls, logs_dir):
        from trello_backup.utils import DateUtils
        session_dir = os.path.join(logs_dir, f"session-{DateUtils.get_current_datetime()}")
        os.makedirs(session_dir)
        LOG.debug("Session dir: %s", session_dir)
        return session_dir

# TODO ASAP2 use this constant
CTX_LOG_LEVEL = 'loglevel'

# TODO ASAP2 use this constant
CTX_WORKING_DIR = 'workingDir'

# TODO ASAP2 use this constant
CTX_SESSION_DIR = 'sessionDir'

# TODO ASAP2 use this constant
CTX_LOG_FILES = "logFiles"

# TODO ASAP2 use this constant
CTX_DRY_RUN = 'dryRun'

CTX_HANDLER = 'handler'