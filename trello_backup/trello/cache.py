import pickle
from pathlib import Path
from typing import Dict, Optional

from trello_backup.constants import FilePath


class WebpageTitleCache:
    def __init__(self, file_path: str = FilePath.WEBPAGE_TITLE_CACHE_FILE):
        """
        Initializes the cache and sets the file path.
        The actual data structure is initialized in the load method.
        """
        self._data: Dict[str, str] = {}
        self._file_path = file_path

    def load(self) -> None:
        """Loads cache data from disk."""
        try:
            with open(self._file_path, 'rb') as f:
                self._data = pickle.load(f)
        except (FileNotFoundError, EOFError, pickle.UnpicklingError):
            self._data = {} # Initialize empty if file is missing or corrupt

    def save(self) -> None:
        """Saves the current cache data to disk."""
        path = Path(self._file_path)
        path.parent.mkdir(parents=True, exist_ok=True) # Ensures the output directory exists

        with open(self._file_path, 'wb') as f:
            pickle.dump(self._data, f, protocol=pickle.HIGHEST_PROTOCOL)

    def get(self, url: str) -> Optional[str]:
        """Retrieves a title for a given URL, or None if not found."""
        # Use the cleaner dict.get() method
        return self._data.get(url)

    def put(self, url: str, title: str) -> None:
        """Stores a title for a given URL."""
        self._data[url] = title