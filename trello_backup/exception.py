class TrelloException(Exception):
    def __init__(self, message, errors=None):
        kwargs = {}
        if errors:
            kwargs["errors"] = errors
        super().__init__(message, **kwargs)


class TrelloConfigException(TrelloException):
    def __init__(self, message, errors=None):
        super().__init__(message, errors)

