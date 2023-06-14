"""
Resource Allocator Client
"""

from abc import abstractmethod
from argparse import ArgumentParser
from dataclasses import dataclass
from getpass import getpass
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
        return Path(self._paths[0]) / (self.server.replace("/", "") + ".json")

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
        email: str,
        password: str | None = None,
        azure_login: bool | None = None,
    ):
        assert (
            (password is not None) | azure_login
        ), "Either email and password or azure_login must be given"

        self.server = server.rstrip("/")
        self.email = email
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
            logger.error(f"Request returned a non-ok exit status: {result.status_code}")
            logger.info(f"Error details: {result.json()}")

        return result.json()

    def register(self, method: str, **data) -> dict[str, Any]:
        """
        Register in a server using email-password login OR Azure Active Directory login

        Args:
            method: str: email or azure
            data: keyword arguments to pass on
        """
        raise NotImplementedError()

    def login(self) -> None:
        """
        Log into an instance using email-password login or Azure Active Directory login

        Args:
            method: email or azure
            data: keyword arguments to pass on
        """
        if self.azure_login:
            return self._login_azure()

        return self._login_email(email=self.email, password=self.password)

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
        code = parse_qs(url.query)["code"][0]
        login_finish = self._make_request(
            method="POST",
            endpoint="login_azure",
            code=code,
            email=self.email,
        )
        self.token = login_finish["token"]
        self.cache.token = self.token
        self.cache.write()

    def _login_email(self, email: str, password: str) -> dict[str, Any]:
        result = self._make_request(
            method="POST",
            endpoint="login",
            email=email,
            password=password,
        )
        self.token = result["token"]
        self.cache.token = self.token
        self.cache.write()

    def list_items(self, endpoint: str) -> dict[str, Any]:
        result = self._make_request(method = "GET", endpoint=endpoint)
        return result

    def get(self, endpoint: str, id: int) -> dict[str, Any]:
        result = self._make_request(method = "GET", endpoint=endpoint, id=id)
        return result

    def query(self, endpoint: str, **data) -> list[dict[str, Any]]:
        """
        Query an endpoint for field values. Note: the API does not support this at the moment
        """
        items = self.list_items(endpoint)
        return [
            item for item in items
            if all((
                str(item.get(key)).casefold() == str(value).casefold()
                for key, value in data.items()
            ))
        ]

    def create(self, endpoint: str, **data) -> dict[str, Any]:
        query_result = self.query(endpoint=endpoint, **data)
        if query_result:
            return query_result[0]

        result = self._make_request(method="POST", endpoint=endpoint, id=None, **data)
        return result

    def update(self, endpoint: str, id: int, **data) -> None:
        result = self._make_request(method="PUT", endpoint=endpoint, id=id, **data)
        return result

    def delete(self, endpoint: str, id: int) -> None:
        result = self._make_request(method="DELETE", endpoint=endpoint, id=id)
        return result


class Formatter:
    """
    Base class to format output
    """
    @abstractmethod
    def format(self, output: dict) -> None:...


class JsonFormatter(Formatter):
    def format(self, output: dict) -> None:
        print(json.dumps(output, indent=2))


def make_parser() -> ArgumentParser:
    """
    Create the argument parser for the program
    """
    parser = ArgumentParser(prog="resource_allocator_client")
    parser.add_argument("-s", "--server", required=True)
    parser.add_argument("-e", "--email", required=True)
    parser.add_argument("-p", "--password")
    parser.add_argument("-a", "--azure-login", action="store_true")
    #parser.add_argument("-c", "--config")
    parser.add_argument("endpoint", nargs=1, choices=[
        "resources", "resource_groups", "resource_to_group", "iterations", "requests", "allocation",
    ])

    #   Command subparsers
    data_kwargs = dict(dest="data", nargs="*", metavar="KEY=VALUE")
    subparsers = parser.add_subparsers(
        title="subcommands",
        dest="action",
        required=True,
    )
    list_subparser = subparsers.add_parser("list")

    get_subparser = subparsers.add_parser("get")
    get_subparser.add_argument("id")

    create_subparser = subparsers.add_parser("create")
    create_subparser.add_argument(**data_kwargs)

    delete_subparser = subparsers.add_parser("delete")
    delete_subparser.add_argument("id")

    update_subparser = subparsers.add_parser("update")
    update_subparser.add_argument("id")
    update_subparser.add_argument(**data_kwargs)

    query_subparser = subparsers.add_parser("query")
    query_subparser.add_argument(**data_kwargs)

    return parser


def parse_data_args(args: list[str]) -> dict[str, str]:
    """
    Parser key-value paired data args returned by the argument parser

    Args:
        args: list[str]: list of strings in the form KEY=VALUE

    Returns:
        dict[str, str]
    """
    result = {}
    for item in args:
        if "=" not in item:
            raise ValueError(f"Invalid input. Expect KEY=VALUE. Got: {item}")

        cur_items = item.split("=", maxsplit=1)
        result[cur_items[0].strip()] = cur_items[1].strip()

    return result


def main() -> None:
    """
    Module's main function that is run whenever the module is run on its own from the command line

    Args:
        None

    Returns:
        None
    """
    args = make_parser().parse_args()
    if not args.password and not args.azure_login:
        args.password = getpass(f"Password for {args.email}: ")

    #   Postprocess args
    args.endpoint = args.endpoint[0]

    if "data" in dir(args):
        args.data = parse_data_args(args.data)

    formatter = JsonFormatter()

    client = Client(
        server=args.server,
        email=args.email,
        password=args.password,
        azure_login=args.azure_login,
    )

    client.login()

    if args.action == "list":
        formatter.format(client.list_items(endpoint=args.endpoint))

    elif args.action == "get":
        formatter.format(client.get(endpoint=args.endpoint, id=args.id))

    elif args.action == "query":
        formatter.format(client.query(endpoint=args.endpoint, **args.data))

    elif args.action == "create":
        formatter.format(client.create(endpoint=args.endpoint, **args.data))

    elif args.action == "delete":
        formatter.format(client.delete(endpoint=args.endpoint, id=args.id))

    elif args.action == "update":
        formatter.format(client.update(endpoint=args.endpoint, id=args.id, **args.data))

    else:
        raise ValueError(f"Invalid action: {args.action}")


if __name__ == "__main__":
    main()
