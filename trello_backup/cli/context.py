from dataclasses import dataclass
from typing import Any, Type, Dict, List

import click

from trello_backup.cmd_handler import MainCommandHandler


# TODO ASAP implement dryRun feature (offline?)
# TODO ASAP Check usage for all properties
#   use loglevel property
#   use logFiles property
# Define a structure for each property's configuration
@dataclass(frozen=True) # frozen=True makes the instances immutable
class ContextProperty:
    """Defines the structure for a property in the Click Context."""
    obj_key: str              # The key used internally in self.obj (e.g., 'loglevel')
    attr_name: str            # The name used as the class attribute (e.g., 'log_level')
    attr_type: Type[Any]      # The type hint for the attribute (e.g., int, str, logging.Logger)

# --- SINGLE SOURCE OF TRUTH (Now with Types) ---
# Use a dictionary where the keys are the internal obj_key for easy lookup/iteration
PROPERTY_CONFIG: Dict[str, ContextProperty] = {
    'loglevel': ContextProperty(
        obj_key='loglevel',
        attr_name='log_level',
        attr_type=int # Example Type
    ),
    'logFiles': ContextProperty(
        obj_key='logFiles',
        attr_name='log_files',
        attr_type=List[str]
    ),
    'workingDir': ContextProperty(
        obj_key='workingDir',
        attr_name='working_dir',
        attr_type=str # Example Type
    ),
    'sessionDir': ContextProperty(
        obj_key='sessionDir',
        attr_name='session_dir',
        attr_type=str
    ),
    'backupDir': ContextProperty(
        obj_key='backupDir',
        attr_name='backup_dir',
        attr_type=str
    ),
    'dryRun': ContextProperty(
        obj_key='dryRun',
        attr_name='dry_run',
        attr_type=str
    ),
    'handler': ContextProperty(
        obj_key='handler',
        attr_name='handler',
        attr_type=MainCommandHandler
    ),
}
# -----------------------------

def _create_context_property(prop_config: ContextProperty) -> property:
    """Creates a property object (getter/setter) from the config."""

    def getter(self):
        # Access using the internal obj_key
        return self.obj[prop_config.obj_key]

    def setter(self, v):
        self.obj[prop_config.obj_key] = v

    return property(getter, setter)


class ClickContextWrapper(click.Context):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# --- Dynamic Injection Phase ---

# 1. Dynamically update __annotations__ for IDE/Linter type hints
for config in PROPERTY_CONFIG.values():
    # Use the specific type hint from the configuration
    ClickContextWrapper.__annotations__[config.attr_name] = config.attr_type

# 2. Dynamically attach the *actual* properties (getters/setters)
for config in PROPERTY_CONFIG.values():
    # This sets ClickContextWrapper.log_level = property(...)
    setattr(ClickContextWrapper, config.attr_name, _create_context_property(config))



class TrelloGroup(click.Group):
    def __init__(self, **kwargs: Any):
        # TODO ASAP logging remove or move to DEBUG log
        print("***created TrelloGroup")
        super().__init__(**kwargs)

    """A custom Group class that ensures all its contexts are of type ClickContextWrapper."""

    # 🎯 This is the key line, exactly as shown in the Click source test!
    context_class = ClickContextWrapper

class TrelloCommand(click.Command):
    def __init__(self, **kwargs: Any):
        # TODO ASAP logging remove or move to DEBUG log
        print("***created TrelloCommand")
        super().__init__(**kwargs)

    """A custom Command class that ensures all its contexts are of type ClickContextWrapper."""

    # 🎯 This is the key line, exactly as shown in the Click source test!
    context_class = ClickContextWrapper



