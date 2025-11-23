#!/usr/bin/env bash

function setup-vars {
    # Replace this with the dir of your choice
    PROJECT_REPO_ROOT=""
    export PROJECT_REPO_ROOT="$HOME/development/my-repos/trello-backup/"
}

function trello-backup {
    ORIG_PYTHONPATH=$PYTHONPATH
    unset PYTHONPATH

    cd $PROJECT_REPO_ROOT
    venv_path="$(poetry env info --path)""/bin/activate"

    source $venv_path
    python -m trello_backup.cli.cli "$@"

    # Cleanup
    deactivate
    PYTHONPATH=$ORIG_PYTHONPATH
}

## Execute setup
setup-vars
