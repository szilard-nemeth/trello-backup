import random
import string


class TestUtils:
    @staticmethod
    def generate_trello_like_id(length=8):
        charset = string.ascii_letters + string.digits   # A-Z a-z 0-9  (62 chars)
        return ''.join(random.choices(charset, k=length))

    @staticmethod
    def generate_short_url():
        return f"https://trello.com/c/{TestUtils.generate_trello_like_id()}"
