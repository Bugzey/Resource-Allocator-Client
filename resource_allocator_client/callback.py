"""
Callback HTTP server to handle Azure logins
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class CallbackServer(HTTPServer):
    """
    HTTP Server to handle OAuth callbacks
    """
    timeout = 60


class CallbackHandler(BaseHTTPRequestHandler):
    """
    HTTP Callback handler to intercept redirections from Azure Active Directory
    """
    code: list = None

    def do_GET(self):
        components = urlparse(self.path)
        query = parse_qs(components.query)
        code = query.get("code", None)

        if code:
            self.code.append(code[0])
            self.send_response(200)
        else:
            self.send_error(400)

        self.end_headers()


def run_callback_server(hostname: str, port: int, variable: list | None = None) -> str:
    """
    Function to start a CallbackServer in order to intercept an OAuth redirect from Azure Active
    Directory

    Args:
        hostname: str: host name to bind to
        port: int: port to bind to
        variable: list: mutable list in which to insert the result. Used when running this function
            in a thread [default: None]

    Returns:
        str: the code returned in the OAuth redirection
    """
    if variable is None:
        variable = []
    CallbackHandler.code = variable
    with CallbackServer((hostname, port), CallbackHandler) as httpd:
        httpd.handle_request()

    return variable[0]
