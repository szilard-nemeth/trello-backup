import atexit
import logging

from trello_backup.display.console import CliLogger

HTTP_SERVER_PORT = 8000

LOG = logging.getLogger(__name__)
CLI_LOG = CliLogger(LOG)

class HttpServer:
    def __init__(self, dir):
        atexit.register(self.stop)
        self._dir = dir
        self._httpd = None

    def launch(self):
        import http.server
        import socketserver

        dir = self._dir
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=dir, **kwargs)

        #Handler = http.server.SimpleHTTPRequestHandler

        with socketserver.TCPServer(("", HTTP_SERVER_PORT), Handler) as httpd:
            self._httpd = httpd
            CLI_LOG.info("Serving at port", HTTP_SERVER_PORT)
            httpd.serve_forever()
            httpd.shutdown()

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()