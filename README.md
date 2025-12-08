# trello-backup 

## Installation
In order to use Trello backup, first you need to install its dependencies.
This project uses Poetry for dependency management so you need to [install poetry](https://python-poetry.org/docs/#installation).


1. Install Poetry by following this guide: https://python-poetry.org/docs/#installing-with-the-official-installer
2. Go to the project's root directory and execute `poetry install`
3. If you want to use Poetry's virtualenv in PyCharm or any other IDE, you can check the path of the virtualenv by running `poetry env info`.

Sample output:
```
➜ poetry env info

Virtualenv
Python:         3.12.3
Implementation: CPython
Path:           /Users/szilardnemeth/Library/Caches/pypoetry/virtualenvs/trello-backup-_NTbtRsv-py3.12
Executable:     /Users/szilardnemeth/Library/Caches/pypoetry/virtualenvs/trello-backup-_NTbtRsv-py3.12/bin/python
Valid:          True

Base
Platform:   darwin
OS:         posix
Python:     3.12.3
Path:       /opt/homebrew/opt/python@3.12/Frameworks/Python.framework/Versions/3.12
Executable: /opt/homebrew/opt/python@3.12/Frameworks/Python.framework/Versions/3.12/bin/python3.12
```

Here the path of the virtualenv is:
```
/Users/szilardnemeth/Library/Caches/pypoetry/virtualenvs/trello-backup-_NTbtRsv-py3.12/bin/python
```

### Setting up `trello-backup` as a command
If you completed the installation, you may want to set up some aliases to use the tool more easily.
First, edit `project-setup.sh` and change `PROJECT_REPO_ROOT` to whatever dir your local git checkout is.
Then, you need to execute `source project-setup.sh`

For automatic sourcing this script for your shell, please refer to [this answer](https://stackoverflow.com/a/15126675/1106893).
For instance, add this to your `~/.bashrc`:
```
source $HOME/development/my-repos/trello-backup/project-setup.sh
```
## Features

### Back up all boards
To back up all boards, execute this command:
```shell
trello-backup backup boards
```


### Back up a specific board
To back up board, execute this command:
```shell
trello-backup backup board Cloudera
```


### Print boards

#### To print cards from specific lists
```shell
trello-backup print board Cloudera --filter-list test1 --filter-list test2
```

#### To print all cards from a board
```shell
trello-backup print board Cloudera
```

#### To print all cards from a board (offline mode)
Offline mode works on files from `<project-root>/tests/resources`

```shell
trello-backup --offline print board Cloudera
trello-backup --offline print board "Priorities, Learn, Misc"

trello-backup --offline print board "TODO: Main categories"  > ~/Downloads/trello-plain-text-todo-main-categories.txt
trello-backup --offline print board "Priorities, Learn, Misc" > ~/Downloads/trello-plain-text-backup-priorities-learn-misc.txt
```

### Clean up boards
Prints cards one by one and prompts for confirmation before deleting card.
```shell
trello-backup cleanup board "Priorities, Learn, Misc"
```


# TODO ASAP add more example commands



### Script to save board backup JSON files
TODO Add reference to backup-and-save-to-project-data



## Running unit tests
Go to DEXter's root dir and run the following commands:
```
poetry env use python
poetry run pytest
```


