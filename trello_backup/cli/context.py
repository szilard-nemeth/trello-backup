from typing import Any

import click

# TODO ASAP use loglevel
# TODO ASAP use logFiles
# TODO ASAP use dryRun
# --- SINGLE SOURCE OF TRUTH ---
# 1. Update this dictionary ONLY when adding, removing, or renaming a property.
PROPERTY_KEYS = {
    'loglevel': 'log_level',
    'workingDir': 'working_dir',
    'sessionDir': 'session_dir',
    'backupDir': 'backup_dir',
    'logFiles': 'log_files',
    'dryRun': 'dry_run',
    'handler': 'handler',
}
# -----------------------------

def _create_context_property(key_constant: str) -> property:
    """Creates a property object (getter/setter) for a given key_constant."""

    def getter(self):
        return self.obj[key_constant]

    def setter(self, v):
        # TODO ASAP do I need this or can I store to wrapper directly?
        self.obj[key_constant] = v

    return property(getter, setter)



class ClickContextWrapper(click.Context):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# --- Dynamic Injection Phase ---

# 1. Dynamically update __annotations__ for IDE/Linter type hints
# We iterate over the desired property names and tell Python/IDEs that
# these attributes exist and have a type of 'Any'.
for property_name in PROPERTY_KEYS.values():
    ClickContextWrapper.__annotations__[property_name] = Any

# 2. Dynamically attach the *actual* properties (getters/setters)
for key_constant, property_name in PROPERTY_KEYS.items():
    # This sets ClickContextWrapper.log_level = property(...)
    setattr(ClickContextWrapper, property_name, _create_context_property(key_constant))

    # The IDE/Linter now has the type information, and the runtime has the properties.



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



