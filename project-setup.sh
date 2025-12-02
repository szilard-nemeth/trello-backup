#!/usr/bin/env bash

function trello-backup {
    PROJECT_REPO_ROOT="$HOME/development/my-repos/trello-backup/"
    cd $PROJECT_REPO_ROOT && poetry run python trello_backup/cli/cli.py "$@"
}

# Export the function so it's inherited by subshells.
export -f trello-backup