"""
JavaScript rendering for page titles — same approach as music-manager's JSRenderer
(requests-html). Kept here so trello-backup does not depend on the full music-manager app.

If you later extract a tiny shared package, replace this module with an import from that lib.
"""

from __future__ import annotations

from enum import Enum

from bs4 import BeautifulSoup
from requests import Response
BS4_HTML_PARSER = "html.parser"

try:
    from requests_html import HTMLSession
except ImportError:
    HTMLSession = None  # type: ignore[misc, assignment]


class JavaScriptRenderer(Enum):
    REQUESTS_HTML = "requests-html"
    SELENIUM = "selenium"


class JSRenderer:
    """Mirrors musicmanager.contentprovider.common.JSRenderer."""

    JS_RENDER_TIMEOUT_SECONDS = 20

    def __init__(self, js_renderer_type: JavaScriptRenderer, fb_selenium):
        self.use_requests_html = False
        self.use_selenium = False
        self.fb_selenium = fb_selenium

        if js_renderer_type == JavaScriptRenderer.REQUESTS_HTML:
            self.use_requests_html = True
        elif js_renderer_type == JavaScriptRenderer.SELENIUM:
            self.use_selenium = True

    def render_with_javascript(self, url, force_use_requests=False) -> BeautifulSoup:
        if self.use_requests_html or force_use_requests:
            html_content = JSRenderer._render_with_requests_html(url)
            return BeautifulSoup(html_content, features=BS4_HTML_PARSER)
        if self.use_selenium:
            if self.fb_selenium is None:
                raise RuntimeError("Selenium JS rendering requires fb_selenium (not used in trello-backup).")
            return self.fb_selenium.load_url_as_soup(url)
        raise RuntimeError("JSRenderer is not configured for requests-html or selenium.")

    @classmethod
    def _render_with_requests_html(cls, url: str) -> str:
        if HTMLSession is None:
            raise ImportError(
                "requests-html is not installed. Install trello-backup with extra 'webpage-js-titles'."
            )
        session = HTMLSession()
        resp: Response = session.get(url)
        resp.html.render(timeout=cls.JS_RENDER_TIMEOUT_SECONDS)
        return resp.html.html
