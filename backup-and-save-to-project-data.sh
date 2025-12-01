#!/usr/bin/env bash

# TODO break down to functions
# TODO: CHECK EXIT CODE
### Example output: example-cli-output-backup-boards.txt

# TODO Argument handling
# $1: session-20251201_1806983309
# TODO get lastly modified dir starting with "session-" from /Users/snemeth/trello-backup-output/
# SESSION_DIR="$1"
SESSION_DIR="session-20251201_1806983309"

# TODO Parse today's date from session dir -> 20251201
# DATE=<parsed date from SESSION_DIR>
DATE="20251201"

# ===================================================
# Declare dirs
TRELLO_OUT_DIR_SESSION="$HOME/trello-backup-output/$SESSION_DIR/backups/"
PROJECT_INPUT_DATA_DIR="$HOME/development/my-repos/project-data/input-data/trello-backup/backup/"
PROJECT_INPUT_DATA_DIR_BOARD="$PROJECT_INPUT_DATA_DIR/boards/$DATE"

# ===================================================
# 1. Backup first
trello-backup backup boards

# ===================================================
# 2. Copy board jsons
mkdir -p "$PROJECT_INPUT_DATA_DIR_BOARD"
# TODO Not sure if this matching works from ZSH
cp -R "$TRELLO_OUT_DIR_SESSION/board-*.json" $PROJECT_INPUT_DATA_DIR_BOARD


# ===================================================
# 3. Update latest symlinks in PROJECT_INPUT_DATA_DIR
ln -s $PROJECT_INPUT_DATA_DIR_BOARD "$PROJECT_INPUT_DATA_DIR/boards/latest"



# ===================================================
# 4. Add links to newly saved files in this repo
TEST_RESOURCES_DIR="$HOME/development/my-repos/trello-backup/tests/resources"

# Remove original symlinks
rm "$TEST_RESOURCES_DIR/boards/*"
# TODO  Would this work for all files to be symlinked?
# TODO Is there a smarter solution this e.g. to only link latest for each type, instad of linking all the files with symlinks?
ln -s "$PROJECT_INPUT_DATA_DIR/boards/latest/*" "$TEST_RESOURCES_DIR/boards/"
ln -s "$PROJECT_INPUT_DATA_DIR/attachments/latest/*" "$TEST_RESOURCES_DIR/attachments/"

# TODO Print Git commit instructions in project-input-data
# TODO link whole folder instead to $HOME/development/my-repos/project-data/input-data/trello-backup/latest
cp -R $TRELLO_OUT_DIR_SESSION ~/Downloads/