from random import random
from typing import Iterable

from rich.prompt import Confirm, Prompt


class PromptFormat:
    def __init__(self, ctx):
        self._prefix = None
        self._ctx = ctx

    def question_italic(self, q):
        return f"{self.prefix()}[i]{q}[/i]?"

    def prefix(self):
        if self._prefix:
            # Assume that cls._ctx is only set once!
            return self._prefix
        if self.is_dry_run():
            self._prefix = "[DRY-RUN] "
            return self._prefix
        return ""

    def is_dry_run(self):
        if self._ctx and self._ctx.dry_run:
            return True
        return False


class PromptHandler:
    def ask_q(self, q: str, default=False):
        pass

    def ask_num(self, q: str, num: str):
        pass

    def prompt(self, q, default=None):
        pass

    def prompt_ask(self, q, default=False):
        pass

    def choices(self, q, choices=Iterable[str]):
        pass

    def _question_number(self, q, num):
        pass


class DefaultPromptHandler(PromptHandler):
    def __init__(self, format: PromptFormat):
        self._format = format

    def ask_q(self, q: str, default=False):
        return self.prompt_ask(q, default=default)

    def ask_num(self, q: str, num: str):
        return Prompt.ask(self._question_number(q, num))

    def prompt(self, q, default=None):
        return Prompt.ask(q, default=default)

    def prompt_ask(self, q, default=False):
        return Confirm.ask(self._format.question_italic(q), default=default)

    def choices(self, q, choices=Iterable[str]):
        return Prompt.ask(self._format.question_italic(q), choices=choices)

    def _question_number(self, q, num):
        return f"{self._format.prefix()}{q}. Enter the following number to proceed: [b]{num}[/b]"


class FakePromptHandler(PromptHandler):
    def ask_q(self, q: str, default=False):
        print(q)
        return True

    def ask_num(self, q: str, num: str):
        print(self._question_number(q, num))
        return num

    def prompt(self, q, default=None):
        print(q)
        return True

    def prompt_ask(self, q, default=False):
        print(q)
        return True

    def choices(self, q, choices=Iterable[str]):
        choice = choices[0]
        print(f"{q}. Choice: {choice}")
        return choice

    def _question_number(self, q, num):
        return f"{q}. Enter the following number to proceed: {num}"


class TrelloPrompt:
    _ctx = None
    _handler = DefaultPromptHandler(PromptFormat(ctx=_ctx))

    @classmethod
    def safe_prompt(cls, q1, q2, ask_q2: bool):
        confirmed = False
        if cls._handler.ask_q(q1, default=True):
            if ask_q2:
                rand_num = random()
                rand_num = str(1000000 * rand_num)[:-4]
                result = cls._handler.ask_num(q2, rand_num)
                if result == rand_num:
                    confirmed = True
            else:
                confirmed = True
        return confirmed

    @classmethod
    def prompt(cls, q, default=None):
        return cls._handler.prompt(q, default=default)

    @classmethod
    def prompt_ask(cls, q, default=False):
        return cls._handler.prompt_ask(q, default=default)

    @classmethod
    def choices(cls, q, choices=Iterable[str]):
        return cls._handler.choices(q, choices=choices)

    @classmethod
    def set_context(cls, new_ctx):
        cls._ctx = new_ctx
        if cls._is_dry_run():
            cls._handler = FakePromptHandler()
        else:
            cls._handler = DefaultPromptHandler(PromptFormat(ctx=cls._ctx))

    @classmethod
    def _is_dry_run(cls):
        if cls._ctx and cls._ctx.dry_run:
            return True
        return False
