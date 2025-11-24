import logging
from collections import defaultdict
from typing import List, Any, Dict

from rich.table import Table

from trello_backup.display.console import CliLogger

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)


class TrelloTableColumnStyles:
    def __init__(self):
        self._color_by_value: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._style_by_value: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._style_dict_per_column: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def bind_style(self, col_name: str, value: str, color: str, style_dict: Dict[str, Any]=None):
        self._color_by_value[col_name][value] = color
        if style_dict:
            if col_name in self._style_dict_per_column:
                self._style_dict_per_column[col_name].update(style_dict)
            else:
                self._style_dict_per_column[col_name] = style_dict
        return self

    def add_format_to_column(self, col: str, no_wrap: bool = False):
        self._style_dict_per_column[col]["no_wrap"] = no_wrap
        return self

    # TODO add new method for justify, and other arbitrary styles?

    def style_by_value(self, col: str, val: str):
        try:
            style = self._style_by_value[col][val]
        except KeyError:
            style = ""
        return style

    def color_by_value(self, col: str, val: str):
        try:
            color = self._color_by_value[col][val]
        except KeyError:
            color = ""
        return color

    def get_column_style_dict(self, col):
        return self._style_dict_per_column[col]


class TrelloTableRenderSettings:
    def __init__(self,
                 col_styles: TrelloTableColumnStyles,
                 wide_print=False,
                 show_lines=False,
                 additional_table_config: Dict[str, Any] = None):
        if not col_styles:
            raise ValueError("col_styles cannot be None!")
        self._col_styles: TrelloTableColumnStyles = col_styles
        self._wide_print = wide_print
        self._show_lines = show_lines

    def format_value(self, col: str, val: str):
        style = self._col_styles.style_by_value(col, val)
        color = self._col_styles.color_by_value(col, val)
        if style:
            rich_style = f"[{style} {color}]"
        elif color:
            rich_style = f"[{color}]"
        else:
            rich_style = ""
        return f"{rich_style}{val}"

    def get_column_style_dict(self, col_name: str):
        return self._col_styles.get_column_style_dict(col_name)

    def get_table_config_dict(self):
        return {"show_lines": self._show_lines}


class TrelloTable:
    # TODO Borrow type-safe and order-safe solution from trello-backup project
    def __init__(self, cols: List[str], render_settings: TrelloTableRenderSettings, title=""):
        self._render_settings: TrelloTableRenderSettings = render_settings
        self._cols = cols
        self._rows = None
        self._table = Table(title=title, **self._render_settings.get_table_config_dict())

        for col in cols:
            # https://rich.readthedocs.io/en/stable/tables.html#column-options
            col_style_dict = self._render_settings.get_column_style_dict(col)
            self._table.add_column(col, **col_style_dict)

    def render(self, rows: List[List[Any]]):
        self._rows = rows
        for row in self._rows:
            # TODO Write unit test, what if row data is changed, would columns be misaligned?
            vals = [self._render_settings.format_value(self._cols[idx], val) for idx, val in enumerate(row)]
            self._table.add_row(*vals)

    def print(self):
        CLI_LOG.print(self._table, wide_print=self._render_settings._wide_print)
