import pickle
import shelve
from pathlib import Path
from typing import Dict, Optional

from trello_backup.constants import FilePath


class WebpageTitleCache:
    def __init__(self, file_path: str = FilePath.WEBPAGE_TITLE_CACHE_FILE):
        """
        Initializes the cache by opening the shelf file.

        The 'shelve.open()' function automatically creates the file
        if it doesn't exist and opens it in read/write mode.
        """
        # The shelf object acts exactly like a dictionary
        # writeback=True ensures that changes to the cache are held in memory
        # until close() or sync() is called.
        self._shelf = shelve.open(file_path, writeback=True)
        # Store the path in case we need it
        self._file_path = file_path

    # --- Cleanup and Persistence ---

    def save(self) -> None:
        """
        Saves any cached changes to disk.
        For a shelve object opened with writeback=True, sync() forces the data
        from memory to be written to the file.
        """
        self._shelf.sync()

    def close(self) -> None:
        """
        Closes the shelf file, ensuring all data is persisted.
        This should always be called when the cache is no longer needed.
        """
        self._shelf.close()

    def __enter__(self):
        """Allows use with the 'with' statement."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensures the shelf is closed automatically when exiting a 'with' block."""
        self.close()

    # Optional: Implement basic dictionary methods for better compatibility
    def __len__(self) -> int:
        return len(self._shelf)

    def __contains__(self, url: str) -> bool:
        return url in self._shelf

    def get(self, url: str) -> Optional[str]:
        """
        Retrieves a title. Handled directly by the shelf object.
        dict.get() handles the 'key not found' case, returning None.
        """
        return self._shelf.get(url)

    def put(self, url: str, title: str) -> None:
        """
        Stores a title. Handled directly by the shelf object.
        """
        self._shelf[url] = title