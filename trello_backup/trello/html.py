import re

from bs4 import BeautifulSoup
import requests

import logging
LOG = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 5
BS4_HTML_PARSER = "html.parser"


class HtmlParser:
    js_renderer = None

    @classmethod
    def configure_webpage_js_renderer(cls, enabled: bool) -> None:
        """
        When enabled, attaches the same requests-html based JSRenderer used in music-manager.
        Requires optional dependency: pip install 'trello-backup[webpage-js-titles]'.
        """
        cls.js_renderer = None
        if not enabled:
            return
        try:
            from trello_backup.trello.js_renderer import JSRenderer, JavaScriptRenderer
        except ImportError as e:
            LOG.warning(
                "webpage-js-titles could not load JS renderer (%s). Install optional extra webpage-js-titles.",
                e,
            )
            return
        cls.js_renderer = JSRenderer(JavaScriptRenderer.REQUESTS_HTML, fb_selenium=None)
        LOG.debug("JS webpage renderer (requests-html) enabled for URL titles.")

    @classmethod
    def fetch_page_title(cls, url: str, *, js_fallback: bool = False):
        """
        Fast path via HTTP first; optional JS (requests-html) when the static title is a known shell.
        """
        title = cls.get_title_from_url(url)
        if not js_fallback or cls.js_renderer is None:
            return title
        if not cls._title_needs_js_fallback(title):
            return title
        js_title = cls.get_title_from_url_with_js(url)
        return js_title if js_title else title

    @staticmethod
    def _title_needs_js_fallback(title: str | None) -> bool:
        if title is None:
            return True
        t = str(title).strip()
        if not t:
            return True
        # YouTube and similar SPAs often serve an empty/placeholder <title> before JS runs.
        if re.fullmatch(r"-?\s*YouTube", t):
            return True
        return False

    @classmethod
    def get_title_from_url(cls, url):
        """
        If page title can't be parsed, fall back to original URL.
        :param url:
        :return:
        """
        LOG.debug("Getting webpage title for URL: {}".format(url))
        try:
            soup = HtmlParser._create_bs_from_url(url)
        except requests.exceptions.ConnectionError as e:
            LOG.error("Failed to get webpage title from URL: " + url)
            return None
        except requests.exceptions.Timeout as e:
            LOG.error("Failed to get webpage title from URL (timeout): " + url)
            return None
        if soup.title is None:
            return None
        title = soup.title.string
        LOG.debug("Found webpage title: {}".format(title))
        return str(title)

    @staticmethod
    def _create_bs_from_url(url, headers=None):
        resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
        soup = HtmlParser._create_bs(resp.text)
        return soup

    @staticmethod
    def _create_bs(html) -> BeautifulSoup:
        return BeautifulSoup(html, features=BS4_HTML_PARSER)

    @classmethod
    def get_title_from_url_with_js(cls, url):
        if cls.js_renderer is None:
            LOG.debug("JS title fetch skipped (no js_renderer): %s", url)
            return None
        LOG.debug("Getting webpage title with JS for URL: %s", url)
        try:
            soup = cls.js_renderer.render_with_javascript(url, force_use_requests=True)
        except Exception as e:
            LOG.error("Failed to get webpage title with JS from URL: %s (%s)", url, e)
            return None
        if soup.title is None:
            return None
        title = soup.title.get_text(strip=True) if soup.title else None
        if not title:
            return None
        LOG.debug("Found webpage title (JS): %s", title)
        return str(title)
