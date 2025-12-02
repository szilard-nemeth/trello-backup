#!/usr/bin/env bash

# --- Configuration ---
PROJECT_INPUT_DATA_BASEDIR="$HOME/development/my-repos/project-data/input-data/trello-backup"
TEST_RESOURCES_DIR="$HOME/development/my-repos/trello-backup/tests/resources"

# --- Functions ---

# Function to find the most recently modified directory starting with "session-"
find_latest_session_dir() {
    local base_path="$HOME/trello-backup-output"
    # Find the latest session dir, handling case where none is found
    LATEST_SESSION=$(find "$base_path" -maxdepth 1 -type d -name "session-*" -exec stat -f "%m %N" {} \; | sort -nr | head -n 1 | awk '{print $NF}' | xargs basename)

    if [[ -z "$LATEST_SESSION" ]]; then
        echo "Error: No 'session-' directory found in $base_path." >&2
        return 1
    fi
    echo "$LATEST_SESSION"
    return 0
}

# Function to parse the date from the session directory name
parse_date_from_session() {
    local session_dir="$1"
    # Extracts the date (YYYYMMDD) assuming the format 'session-YYYYMMDD_...'
    if [[ "$session_dir" =~ session-([0-9]{8}_[0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}"
        return 0
    else
        echo "Error: Could not parse date from session directory name: $session_dir" >&2
        return 1
    fi
}

# Handles script arguments and sets essential variables
handle_arguments() {
    if [[ -n "$1" ]]; then
        SESSION_DIR="$1"
    else
        # get last modified dir starting with "session-" from $HOME/trello-backup-output/
        SESSION_DIR=$(find_latest_session_dir)
        if [[ $? -ne 0 ]]; then
            exit 1
        fi
    fi

    # Parse today's date from session dir
    DATE=$(parse_date_from_session "$SESSION_DIR")
    if [[ $? -ne 0 ]]; then
        exit 1
    fi

    # Declare dirs (using absolute paths for clarity)
    export TRELLO_OUT_DIR_SESSION="$HOME/trello-backup-output/$SESSION_DIR/backups"
    export PROJECT_INPUT_DATA_DIR_BOARD="$PROJECT_INPUT_DATA_BASEDIR/backup/boards/$DATE"

    echo "Using Session Dir: $SESSION_DIR"
    echo "Using Date: $DATE"
    echo "Target Board Dir: $PROJECT_INPUT_DATA_DIR_BOARD"
}

# Executes the trello-backup command
backup_trello() {
    echo "==================================================="
    echo "1. Backing up Trello boards..."
    trello-backup backup boards
    if [[ $? -ne 0 ]]; then
        echo "Error: Trello backup failed." >&2
        return 1
    fi
    return 0
}

# Copies board JSON files to the project input data directory
copy_board_jsons() {
    echo "==================================================="
    echo "2. Copying board jsons to $PROJECT_INPUT_DATA_DIR_BOARD..."

    mkdir -p "$PROJECT_INPUT_DATA_DIR_BOARD"

    # TODO Not sure if this matching works from ZSH - Using 'shopt -s nullglob' and 'cp' is generally robust.
    # The '*' in bash/zsh expands before cp runs. The '-R' is unnecessary for copying files.
    # Using 'cp' with a relative path pattern works reliably across shells.
    local files_copied=0

    # Use 'find' to get files to ensure compatibility and robustness
    find "$TRELLO_OUT_DIR_SESSION" -maxdepth 1 -name "board-*.json" -exec cp {} "$PROJECT_INPUT_DATA_DIR_BOARD" \;

    # Check if any files were actually copied (optional, but good practice)
    if [[ -z "$(ls -A "$PROJECT_INPUT_DATA_DIR_BOARD"/board-*.json 2>/dev/null)" ]]; then
         echo "Warning: No 'board-*.json' files found or copied from $TRELLO_OUT_DIR_SESSION."
    else
         echo "Successfully copied board JSON files."
    fi

    # This was the original file copy command (better for ZSH/Bash compatibility)
    # cp "$TRELLO_OUT_DIR_SESSION"/board-*.json "$PROJECT_INPUT_DATA_DIR_BOARD"

    return 0
}

# Updates the 'latest' symlink to point to the current date's directory
update_latest_symlink() {
    echo "==================================================="
    echo "3. Updating 'latest' symlink..."

    local latest_symlink="$PROJECT_INPUT_DATA_BASEDIR/backup/boards/latest"

    # Remove existing symlink if it exists
    rm -f "$latest_symlink"

    # Linking the whole folder is better for consistency.
    ln -s "$PROJECT_INPUT_DATA_DIR_BOARD" "$latest_symlink"

    echo "Created symlink: $latest_symlink -> $PROJECT_INPUT_DATA_DIR_BOARD"
    return 0
}

# Updates symlinks in the test resources directory
update_test_resources() {
    echo "==================================================="
    echo "4. Updating test resources symlinks..."

    local test_board_dir="$TEST_RESOURCES_DIR/boards"
    local latest_board_dir="$PROJECT_INPUT_DATA_BASEDIR/backup/boards/latest"

    # Remove all existing links/files in the test resources board directory
    rm -f "$test_board_dir"/*

    # TODO Is there a smarter solution this e.g. to only link latest for each type, instead of linking all the files with symlinks?
    # Linking the entire 'latest' folder contents is the simplest way.
    # The use case suggests you *do* want all latest files for testing, so linking all is correct here.

    # The shell expands "$latest_board_dir/*" to a list of files before 'ln -s' is executed.
    ln -s "$latest_board_dir"/* "$test_board_dir/"

    # TODO Also symlink attachments
    # Placeholder for attachments (assuming they exist, if not, this will fail silently/harmlessly)
    # ln -s "$PROJECT_INPUT_DATA_BASEDIR/attachments/latest"/* "$TEST_RESOURCES_DIR/attachments/"

    echo "Symlinks in $test_board_dir updated."
    return 0
}

# Prints instructions for the next steps
print_commit_instructions() {
    echo "==================================================="
    echo "TODO Print Git commit instructions in project-input-data"
    echo "Next steps: Commit the new data in the 'project-data' repository."
    echo "cd $PROJECT_INPUT_DATA_BASEDIR"
    echo "git add backup/boards/$DATE"
    echo "git commit -m \"Trello backup: $DATE\""
    echo "git push"
    echo "==================================================="
}

# --- Main Script Execution ---

main() {
    handle_arguments "$1"

    # Check for script errors before continuing
    if [[ $? -ne 0 ]]; then
        exit 1
    fi

    backup_trello || exit 1 # Exit if backup fails
    copy_board_jsons || exit 1 # Exit if copy fails
    update_latest_symlink || exit 1 # Exit if symlink fails
    update_test_resources || exit 1 # Exit if test resources update fails

    cp -R $TRELLO_OUT_DIR_SESSION "$HOME/Downloads/trello-backup-$SESSION_DIR"
    echo "Copied files to $HOME/Downloads/"

    print_commit_instructions
}

main "$1"