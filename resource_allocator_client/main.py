"""
Resource Allocator Client
"""

from argparse import ArgumentParser
from dataclasses import dataclass
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs
import webbrowser

import requests as req


logger = logging.getLogger(__name__)


class CallbackServer(HTTPServer):
    timeout = 60


class CallbackHandler(BaseHTTPRequestHandler):
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

def run_callback_server(code_list: list):
    CallbackHandler.code = code_list
    with CallbackServer(("localhost", 8080), CallbackHandler) as httpd:
        httpd.handle_request()

    breakpoint()
    return code_list[0]


@dataclass
class Cache:
    server: str
    token: str = None

    _paths = [
        Path("."),
    ]

    @property
    def path(self):
        return Path(self._paths[0]) / self.server.replace("/", "")

    def read(self):
        path = self.path
        if path.exists():
            with open(path) as cur_path:
                data = json.load(cur_path)
            self.token = data["token"]

        return data

    def write(self):
        path = self.path
        with open(path, "w") as cur_path:
            _ = json.dump(self.__dict__, cur_path)


class Client:
    def __init__(
        self,
        server: str,
        username: str,
        password: str | None = None,
        azure_login: bool | None = None,
    ):
        assert server.startswith("http")
        assert (
            (password is not None) | azure_login
        ), "Either username and password or azure_login must be given"

        self.server = server.rstrip("/")
        self.username = username
        self.password = password
        self.azure_login = azure_login
        self.cache = Cache(server=self.server)

    def _make_request(
        self,
        method: str,
        endpoint: str,
        id: int | None = None,
        **data,
    ) -> req.PreparedRequest:

        endpoint = endpoint.strip("/")
        url = f"{self.server}/{endpoint}/"

        if id:
            url = f"{url}{id}"

        result = req.request(
            method = method,
            url = url,
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cache.token}",
            },
            json = data,
        )
        if not result.ok:
            message = f"Error making the request. Status: {result.status_code}, json: {result.json()}"
            logger.error(message)
            raise RuntimeError(message)

        return result.json()

    def register(self, method: str, **data) -> dict[str, Any]:
        """
        Register in a server using username-password login OR Azure Active Directory login

        Args:
            method: str: username or azure
            data: keyword arguments to pass on
        """
        raise NotImplementedError()

    def login(self) -> None:
        """
        Log into an instance using username-password login or Azure Active Directory login

        Args:
            method: username or azure
            data: keyword arguments to pass on
        """
        if self.azure_login:
            return self._login_azure()

        return self._login_username(username=self.username, password=self.password)

    def _login_azure(self):
        #   TODO: split later

        #   Get auth URL and redirect
        login_init = self._make_request(
            method="GET",
            endpoint="login_azure",
        )
        auth_url = login_init["auth_url"]

        #   Ask user to paste the redirect 
        if not webbrowser.open(auth_url):
            print(f"Please visit the following URL: {auth_url}")

        url = urlparse(input("Paste redirect URL: "))
        breakpoint()
        code = parse_qs(url.query)["code"][0]
        login_finish = self._make_request(
            method="POST",
            endpoint="login_azure",
            code=code,
            email=self.username,
        )
        self.token = login_finish["token"]
        self.cache.token = self.token
        self.cache.write()

    def _login_username(self, username: str, password: str) -> dict[str, Any]:
        result = self._make_request(
            method="POST",
            endpoint="login",
            username=username,
            password=password,
        )
        self.token = result["token"]
        self.cache.token = self.token
        self.cache.write()

    def list_items(self) -> dict[str, Any]:
        result = self._make_request(method = "GET")
        return result

    def get(self, id: int) -> dict[str, Any]:
        result = self._make_request(method = "GET", id = id)
        return result

    def query(self, **data) -> list[dict[str, Any]]:
        """
        Query an endpoint for field values. Note: the API does not support this at the moment
        """
        items = self.list_items()
        return [
            item for item in items if all((item.get(key) == value for key, value in data.items()))
        ]

    def create(self, **data) -> dict[str, Any]:
        query_result = self.query(**data)
        if query_result:
            return query_result[0]

        result = self._make_request(method = "POST", id = None, **data)
        return result

    def update(self, id: int, **data) -> None:
        pass

    def delete(self, id: int) -> None:
        pass


def make_parser() -> ArgumentParser:
    """
    Create the argument parser for the program
    """
    parser = ArgumentParser()
    parser.add_argument("-s", "--server", required=True)
    parser.add_argument("-u", "--username", required=True)
    parser.add_argument("-p", "--password")
    parser.add_argument("-a", "--azure-login", action="store_true")
    #parser.add_argument("-c", "--config")
    return parser


def main() -> None:
    """
    Module's main function that is run whenever the module is run on its own from the command line

    Args:
        None

    Returns:
        None
    """
    args = make_parser().parse_args()
    client = Client(
        server=args.server,
        username=args.username,
        password=args.password,
        azure_login=args.azure_login,
    )
    client.login()
    breakpoint()


if __name__ == "__main__":
    main()
