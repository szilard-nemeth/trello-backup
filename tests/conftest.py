from typing import Iterator

import pytest
from _pytest.capture import CaptureFixture
from click.testing import CliRunner, Result

"""
https://docs.pytest.org/en/stable/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files
"""

class PyTestCliRunner(CliRunner):
    """Override CliRunner to disable capsys
    Please refer to: https://github.com/pallets/click/issues/824#issuecomment-1855594390
    """

    def __init__(self, capsys):
        super().__init__()
        self.capsys = capsys

    def invoke(self, *args, **kwargs) -> Result:
        # Way to fix https://github.com/pallets/click/issues/824
        with self.capsys.disabled():
            result = super().invoke(*args, **kwargs)
        return result


@pytest.fixture
def click_runner(capsys: CaptureFixture[str]) -> Iterator[CliRunner]:
    """
    Convenience fixture to return a click.CliRunner for cli testing
    """

    runner = PyTestCliRunner(capsys)
    runner.capsys = capsys
    yield runner
