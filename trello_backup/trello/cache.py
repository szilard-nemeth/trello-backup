import pickle
from typing import Dict

from trello_backup.constants import FilePath


class WebpageTitleCache:
    _DATA = {}

    @staticmethod
    def load() -> Dict[str, str]:
        try:
            with open(FilePath.WEBPAGE_TITLE_CACHE_FILE, 'rb') as handle:
                WebpageTitleCache._DATA = pickle.load(handle)
        except:
            WebpageTitleCache._DATA = {}

    @staticmethod
    def save():
        with open(FilePath.WEBPAGE_TITLE_CACHE_FILE, 'wb') as handle:
            pickle.dump(WebpageTitleCache._DATA, handle, protocol=pickle.HIGHEST_PROTOCOL)