import pickle

from trello_backup.constants import FilePath


class WebpageTitleCache:
    _DATA = {}

    @staticmethod
    def load():
        try:
            with open(FilePath.WEBPAGE_TITLE_CACHE_FILE, 'rb') as f:
                WebpageTitleCache._DATA = pickle.load(f)
        except:
            WebpageTitleCache._DATA = {}

    @staticmethod
    def save():
        with open(FilePath.WEBPAGE_TITLE_CACHE_FILE, 'wb') as f:
            pickle.dump(WebpageTitleCache._DATA, f, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def get(url: str):
        return WebpageTitleCache._DATA[url] if url in WebpageTitleCache._DATA else None

    @staticmethod
    def put(url: str, title: str):
        WebpageTitleCache._DATA[url] = title