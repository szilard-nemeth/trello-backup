from bs4 import BeautifulSoup
import requests

import logging
LOG = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 5
BS4_HTML_PARSER = "html.parser"

class HtmlParser:
    js_renderer = None

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
            LOG.error("Failed to get page title from URL: " + url)
            return url
        except requests.exceptions.Timeout as e:
            LOG.error("Failed to get page title from URL (timeout): " + url)
            return url
        if soup.title is None:
            return url
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
        soup = HtmlParser.js_renderer.render_with_javascript(url, force_use_requests=True)
        title = soup.title.string
        return title
