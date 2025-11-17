HTTP_SERVER_PORT = 8000


class HttpServer:
    INSTANCE = None

    @staticmethod
    def launch_http_server(dir):
        import http.server
        import socketserver

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=dir, **kwargs)

        #Handler = http.server.SimpleHTTPRequestHandler

        with socketserver.TCPServer(("", HTTP_SERVER_PORT), Handler) as httpd:
            HttpServer.INSTANCE = httpd
            print("serving at port", HTTP_SERVER_PORT)
            httpd.serve_forever()
            httpd.shutdown()

    @staticmethod
    def stop_server():
        if HttpServer.INSTANCE:
            HttpServer.INSTANCE.shutdown()