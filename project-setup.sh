#!/usr/bin/env bash

function trello-backup {
    PROJECT_REPO_ROOT="$HOME/development/my-repos/trello-backup/"
    cd "$PROJECT_REPO_ROOT" && poetry run python -m trello_backup.cli.cli "$@"
}

# Export the function so it's inherited by subshells.
# Guarded because `export -f` is a bash-ism. In zsh, `export` is `typeset -x`,
# and `-f` in the typeset family means "print function definition" — so
# unguarded `export -f trello-backup` dumps the whole function body at every
# sourcing (visible when this file is sourced from a zsh startup file).
if [ -n "$BASH_VERSION" ]; then
    export -f trello-backup
fi