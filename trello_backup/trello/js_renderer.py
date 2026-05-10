"""
JavaScript rendering for page titles — same approach as music-manager's JSRenderer
(requests-html). Kept here so trello-backup does not depend on the full music-manager app.

If you later extract a tiny shared package, replace this module with an import from that lib.
"""

from __future__ import annotations

import logging
import pickle

from selenium import webdriver
from selenium.common import ElementNotVisibleException, ElementNotSelectableException, NoSuchElementException, \
    TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from trello_backup.trello.html import HtmlParser

LOG = logging.getLogger(__name__)

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

    def __init__(self, js_renderer_type: JavaScriptRenderer):
        self.use_requests_html = False
        self.use_selenium = False
        self._selenium_loader = SeleniumLoader()

        if js_renderer_type == JavaScriptRenderer.REQUESTS_HTML:
            self.use_requests_html = True
        elif js_renderer_type == JavaScriptRenderer.SELENIUM:
            self.use_selenium = True

    def render_with_javascript(self, url, force_use_requests=False) -> BeautifulSoup:
        if self.use_requests_html or force_use_requests:
            html_content = JSRenderer._render_with_requests_html(url)
            return BeautifulSoup(html_content, features=BS4_HTML_PARSER)
        if self.use_selenium:
            return self._selenium_loader.load_url_as_soup(url)
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


class SeleniumLoader:
    CHROME_OPT_SELENIUM_PROFILE = "user-data-dir=selenium"
    # TODO
    COMMENT_BUTTON_XPATH = '//span[text()="Comment"]'

    def __init__(self):
        self.chrome_options = None
        self.driver = None
        self._init_webdriver()
        self._init_logging()

    @staticmethod
    def _init_logging():
        import logging
        from selenium.webdriver.remote.remote_connection import LOGGER
        LOGGER.setLevel(logging.INFO)

    def load_url_as_soup(self, url, timeout=25, poll_freq=2) -> BeautifulSoup:

        if self.driver.current_url != url:
            self._load_url(poll_freq, timeout, url)
        else:
            LOG.debug("Current URL matches desired URL '%s', not loading again", url)
        html = self.driver.page_source
        return HtmlParser.create_bs(html)

    def _load_url(self, poll_freq, timeout, url):
        self.driver.get(url)
        try:
            wait = WebDriverWait(self.driver, timeout=timeout, poll_frequency=poll_freq,
                                 ignored_exceptions=[NoSuchElementException, ElementNotVisibleException,
                                                     ElementNotSelectableException])
            _ = wait.until(expected_conditions.all_of(
                expected_conditions.element_to_be_clickable((By.XPATH, self.COMMENT_BUTTON_XPATH))))
        except TimeoutException as e:
            raise e

    def _init_webdriver(self):
        if not self.chrome_options:
            self.chrome_options = Options()
            self.chrome_options.add_argument(self.CHROME_OPT_SELENIUM_PROFILE)
        if not self.driver:
            self.driver = webdriver.Chrome(options=self.chrome_options)
