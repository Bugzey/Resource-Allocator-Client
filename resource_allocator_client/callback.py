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


def run_callback_server(code_list: list) -> str:
    """
    Function to start a CallbackServer in order to intercept an OAuth redirect from Azure Active
    Directory

    Args:
        code_list: list object to mutate the code into

    Returns:
        str: the code returned in the OAuth redirection
    """
    CallbackHandler.code = code_list
    with CallbackServer(("localhost", 8080), CallbackHandler) as httpd:
        httpd.handle_request()

    return code_list[0]
