from bs4 import BeautifulSoup
from google.auth.transport import requests
BS4_HTML_PARSER = "html.parser"

class HtmlParser:
    js_renderer = None

    @staticmethod
    def create_bs(html) -> BeautifulSoup:
        return BeautifulSoup(html, features=BS4_HTML_PARSER)

    @staticmethod
    def create_bs_from_url(url, headers=None):
        resp = requests.get(url, headers=headers)
        soup = HtmlParser.create_bs(resp.text)
        return soup

    @classmethod
    def get_title_from_url(cls, url):
        """
        If page title can't be parsed, fall back to original URL.
        :param url:
        :return:
        """
        print("Getting webpage title for URL: {}".format(url))
        try:
            soup = HtmlParser.create_bs_from_url(url)
        except requests.exceptions.ConnectionError as e:
            print("Failed to get page title from URL: " + url)
            return url
        if soup.title is None:
            return url
        title = soup.title.string
        print("Found webpage title: {}".format(title))
        return str(title)

    @classmethod
    def get_title_from_url_with_js(cls, url):
        soup = HtmlParser.js_renderer.render_with_javascript(url, force_use_requests=True)
        title = soup.title.string
        return title
