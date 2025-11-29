from typing import Any

import click


class ClickContextWrapper(click.Context):
    CTX_LOG_LEVEL = 'loglevel'  # TODO ASAP use this constant
    CTX_WORKING_DIR = 'workingDir'
    CTX_SESSION_DIR = 'sessionDir'
    CTX_BACKUP_DIR = "backupDir"
    CTX_LOG_FILES = "logFiles"  # TODO ASAP use this constant
    CTX_DRY_RUN = 'dryRun'  # TODO ASAP use this constant
    CTX_HANDLER = 'handler'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # TODO do I need this or can I store to wrapper directly?
    @property
    def handler(self):
        return self.obj[self.CTX_HANDLER]

    @handler.setter
    def handler(self, v):
        self.obj[self.CTX_HANDLER] = v

    @property
    def dry_run(self):
        return self.obj[self.CTX_DRY_RUN]

    @dry_run.setter
    def dry_run(self, v):
        self.obj[self.CTX_DRY_RUN] = v

    @property
    def log_level(self):
        return self.obj[self.CTX_LOG_LEVEL]

    @log_level.setter
    def log_level(self, v):
        self.obj[self.CTX_LOG_LEVEL] = v

    @property
    def log_files(self):
        return self.obj[self.CTX_LOG_FILES]

    @log_files.setter
    def log_files(self, v):
        self.obj[self.CTX_LOG_FILES] = v

    @property
    def session_dir(self):
        return self.obj[self.CTX_SESSION_DIR]

    @session_dir.setter
    def session_dir(self, v):
        self.obj[self.CTX_SESSION_DIR] = v

    @property
    def backup_dir(self):
        return self.obj[self.CTX_BACKUP_DIR]

    @backup_dir.setter
    def backup_dir(self, v):
        self.obj[self.CTX_BACKUP_DIR] = v

    @property
    def working_dir(self):
        return self.obj[self.CTX_WORKING_DIR]

    @working_dir.setter
    def working_dir(self, v):
        self.obj[self.CTX_WORKING_DIR] = v

class TrelloGroup(click.Group):
    def __init__(self, **kwargs: Any):
        print("***created TrelloGroup")
        super().__init__(**kwargs)

    """A custom Group class that ensures all its contexts are of type ClickContextWrapper."""

    # 🎯 This is the key line, exactly as shown in the Click source test!
    context_class = ClickContextWrapper

class TrelloCommand(click.Command):
    def __init__(self, **kwargs: Any):
        print("***created TrelloCommand")
        super().__init__(**kwargs)

    """A custom Command class that ensures all its contexts are of type ClickContextWrapper."""

    # 🎯 This is the key line, exactly as shown in the Click source test!
    context_class = ClickContextWrapper



