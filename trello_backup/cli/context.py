from dataclasses import dataclass
from typing import Any, Type, Dict, List

import click

from trello_backup.cmd_handler import MainCommandHandler
import logging

from trello_backup.utils import LoggingUtils

# TODO ASAP implement dryRun feature (offline?)
# Define a structure for each property's configuration
@dataclass(frozen=True)
class ContextProperty:
    """Defines the structure for a property in the Click Context."""
    # This single 'name' field is used for both the self.obj key and the external attribute name.
    name: str
    attr_type: Type[Any]      # The type hint for the attribute

# --- SINGLE SOURCE OF TRUTH (List with Unified Naming) ---
PROPERTY_CONFIG: List[ContextProperty] = [
    ContextProperty(
        name='log_level',
        attr_type=str  # Assuming log level is a string like 'INFO', 'DEBUG', etc.
    ),
    ContextProperty(
        name='log_files',
        attr_type=List[str] # Assuming this is a list of file paths
    ),
    ContextProperty(
        name='working_dir',
        attr_type=str
    ),
    ContextProperty(
        name='session_dir',
        attr_type=str
    ),
    ContextProperty(
        name='backup_dir',
        attr_type=str
    ),
    ContextProperty(
        name='dry_run',
        attr_type=bool
    ),
    ContextProperty(
        name='handler',
        attr_type=MainCommandHandler
    ),
]
# -------------------------------------

def _create_context_property(prop_config: ContextProperty) -> property:
    """
    Creates a property object (getter/setter) for self.obj access.
    This function generates the repetitive code.
    """

    def getter(self):
        return self.obj[prop_config.name]

    def setter(self, v):
        self.obj[prop_config.name] = v

    return property(getter, setter)

class ClickContextWrapper(click.Context):
    # Note: We no longer need to manually define CTX_ constants here,
    # as the property names are now defined in PROPERTY_CONFIG.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# --- Dynamic Injection Phase ---

# 1. Dynamically update __annotations__ for IDE/Linter type hints
# This allows autocompletion and type checking on attributes like ctx.log_level
for config in PROPERTY_CONFIG:
    ClickContextWrapper.__annotations__[config.name] = config.attr_type

# 2. Dynamically attach the *actual* properties (getters/setters)
for config in PROPERTY_CONFIG:
    # This sets ClickContextWrapper.log_level = property(...)
    setattr(ClickContextWrapper, config.name, _create_context_property(config))


def log_trello_command_cls_details(cl, kwargs):
    # The 'callback' keyword argument holds the decorated function object!
    decorated_function = kwargs.get('callback')
    LoggingUtils.init_with_basic_config(debug=True, temporary_init=True)
    log = logging.getLogger()
    if decorated_function:
        module_name = decorated_function.__module__
        function_name = decorated_function.__name__
        log.debug("Created %s. Loaded from module: %s, annotated function name: %s",cl.__name__, module_name, function_name)
    else:
        log.debug("Created %s - Could not find decorated function.", cl.__name__)


class TrelloGroup(click.Group):
    """A custom Group class that ensures all its contexts are of type ClickContextWrapper."""
    def __init__(self, **kwargs: Any):
        log_trello_command_cls_details(TrelloGroup, kwargs)
        super().__init__(**kwargs)

    # 🎯 This is the key line, exactly as shown in the Click source test!
    context_class = ClickContextWrapper

class TrelloCommand(click.Command):
    """A custom Command class that ensures all its contexts are of type ClickContextWrapper."""
    def __init__(self, **kwargs: Any):
        log_trello_command_cls_details(TrelloCommand, kwargs)
        super().__init__(**kwargs)

    # 🎯 This is the key line, exactly as shown in the Click source test!
    context_class = ClickContextWrapper



