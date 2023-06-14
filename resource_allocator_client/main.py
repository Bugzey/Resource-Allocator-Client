"""
Resource Allocator Client

Command-line client to query the Resource-Allocator API application
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


@dataclass
class Cache:
    """
    Cache to store and load cached OAuth tokens

    Attributes:
        server: str: address of the Resource-Allocator server
        token: str: token received by the server
    """
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
            with open(path, "r", encoding="utf-8") as cur_path:
                data = json.load(cur_path)
            self.token = data["token"]

        return data

    def write(self):
        path = self.path
        with open(path, "w", encoding="utf-8") as cur_path:
            json.dump(self.__dict__, cur_path)


class Client:
    """
    Resource Allocator Client class to handle all API operations
    """
    def __init__(
        self,
        server: str,
        email: str,
        password: str | None = None,
        azure_login: bool | None = None,
    ):
        """
        Initialize the client. Either password or azure_login must be set

        Args:
            server: str: URL of the Resource Allocator server instance
            email: str: user's email for logging into the server
            password: str: user's password if using password authentication [default: None]
            azure_login: bool: whether to use Azure Active Directory Login [default: None]
        """
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
        """
        Private method to create a request to the API server

        Args:
            method: str: HTTP method. Should be one of GET, POST, PUT, DELETE
            endpoint: str: API endpoint
            id: int: identity of the record to affect [default: None]
            data: dict: keyword arguments to pass in JSON form to the server
        """
        endpoint = endpoint.strip("/")
        url = f"{self.server}/{endpoint}/"

        if id:
            url = f"{url}{id}"

        result = req.request(
            method=method,
            url=url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cache.token}",
            },
            json=data,
            timeout=60,
        )
        if not result.ok:
            logger.error(f"Request returned a non-ok exit status: {result.status_code}")
            logger.info(f"Error details: {result.json()}")

        return result.json()

    def register(self, **data) -> dict[str, Any]:
        """
        Register in a server using email-password login OR Azure Active Directory login

        Args:
            data: keyword arguments to pass on

        Returns:
            dict[str, Any]: API response
        """
        if self.azure_login:
            return self._register_azure(**data)

        return self._register_email(**data)

    def _register_azure(self, **data) -> dict[str, Any]:
        raise NotImplementedError()

    def _register_email(self, **data) -> dict[str, Any]:
        result = self._make_request(
            method="POST",
            endpoint="register",
            email=self.email,
            password=self.password,
            **data,
        )
        if "token" not in result:
            logger.error("Bad register result")
            return result

        self.cache.token = result["token"]
        self.cache.write()
        return result

    def login(self) -> dict[str, Any]:
        """
        Log into an instance using email-password login or Azure Active Directory login

        Args:
            None

        Returns:
            dict[str, Any]: API response
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
        self.cache.token = login_finish["token"]
        self.cache.write()
        return login_finish

    def _login_email(self, email: str, password: str) -> dict[str, Any]:
        result = self._make_request(
            method="POST",
            endpoint="login",
            email=email,
            password=password,
        )
        if "token" not in result:
            logger.error("Bad log-in response")
            return result

        self.cache.token = result["token"]
        self.cache.write()
        return result

    def list_items(self, endpoint: str) -> list[dict[str, Any]]:
        """
        List items from an API endpoint

        Args:
            endpoint: str: address of the API endpoint

        Returns:
            list[dict[str, Any]]: API response
        """
        result = self._make_request(method = "GET", endpoint=endpoint)
        return result

    def get(self, endpoint: str, id: int) -> dict[str, Any]:
        """
        Get a single item from an API endpoint

        Args:
            endpoint: str: address of the API endpoint
            id: int: identity number of the item to retreive

        Returns:
            dict[str, Any]: API response
        """
        result = self._make_request(method = "GET", endpoint=endpoint, id=id)
        return result

    def query(self, endpoint: str, **data) -> list[dict[str, Any]]:
        """
        Query an endpoint for field values. Note: the API does not support this at the moment

        Args:
            endpoint: str: address of the API endpoint
            data: dict: key-value pairs to query against. Return results only if all columns in the
                given data object are equal to the respective columns of the object

        Returns:
            list[dict[str, Any]]: API response
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
        """
        Create an item for an API endpoint

        Args:
            endpoint: str: address of the API endpoint
            data: dict: key-value pairs of data for the created object

        Returns:
            dict[str, Any]: API response
        """
        query_result = self.query(endpoint=endpoint, **data)
        if query_result:
            return query_result[0]

        result = self._make_request(method="POST", endpoint=endpoint, id=None, **data)
        return result

    def update(self, endpoint: str, id: int, **data) -> dict[str, Any]:
        """
        Update an existing item in an API endpoint

        Args:
            endpoint: str: address of the API endpoint
            data: dict: key-value pairs of data for the created object

        Returns:
            dict[str, Any]: API response
        """
        result = self._make_request(method="PUT", endpoint=endpoint, id=id, **data)
        return result

    def delete(self, endpoint: str, id: int) -> None:
        """
        Delete an object from an API endpoint. The response contains the values of the deleted
        record

        Args:
            endpoint: str: address of the API endpoint
            id: int: identity of the record to delete

        Returns:
            dict[str, Any]: API response
        """
        result = self._make_request(method="DELETE", endpoint=endpoint, id=id)
        return result


class Formatter:
    """
    Base class to format output
    """
    @abstractmethod
    def format(self, output: dict) -> None:...


class JsonFormatter(Formatter):
    """
    Formatter-subclass to format and print API responses in JSON format
    """
    def format(self, output: dict) -> None:
        print(json.dumps(output, indent=2))


def make_parser() -> ArgumentParser:
    """
    Create the argument parser for the program

    Args:
        None

    Returns:
        ArgumentParser
    """
    parser = ArgumentParser(
        prog="resource_allocator_client",
        description="Command-line client to query the Resource-Allocator API application",
    )
    parser.add_argument("-s", "--server", required=True, help="Server address")
    parser.add_argument("-e", "--email", required=True, help="User email")
    parser.add_argument("-p", "--password", help="User password. Leave blank for interactive entry")
    parser.add_argument("-a", "--azure-login", action="store_true", help="Log-in via Azure AD")
    #parser.add_argument("-c", "--config", help="Path to a configuration file")

    #   Command subparsers
    endpoint_kwargs = dict(dest="endpoint", nargs=1, choices=[
        "resources", "resource_groups", "resource_to_group", "iterations", "requests", "allocation",
    ])
    data_kwargs = dict(
        dest="data",
        nargs="*",
        metavar="KEY=VALUE",
        help="Key-value pairs to create, update or query",
    )
    id_kwargs = dict(dest="id", help="ID of the item")

    subparsers = parser.add_subparsers(
        title="subcommands",
        dest="action",
        required=True,
    )
    register_subparser = subparsers.add_parser("register")
    register_subparser.add_argument(**data_kwargs)

    _ = subparsers.add_parser("login")

    list_subparser = subparsers.add_parser("list")
    list_subparser.add_argument(**endpoint_kwargs)

    get_subparser = subparsers.add_parser("get")
    get_subparser.add_argument(**endpoint_kwargs)
    get_subparser.add_argument(**id_kwargs)

    create_subparser = subparsers.add_parser("create")
    create_subparser.add_argument(**endpoint_kwargs)
    create_subparser.add_argument(**data_kwargs)

    delete_subparser = subparsers.add_parser("delete")
    delete_subparser.add_argument(**endpoint_kwargs)
    delete_subparser.add_argument(**id_kwargs)

    update_subparser = subparsers.add_parser("update")
    update_subparser.add_argument(**endpoint_kwargs)
    update_subparser.add_argument(**id_kwargs)
    update_subparser.add_argument(**data_kwargs)

    query_subparser = subparsers.add_parser("query")
    query_subparser.add_argument(**endpoint_kwargs)
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
    if "data" in dir(args):
        args.data = parse_data_args(args.data)

    if "endpoint" in dir(args):
        args.endpoint = args.endpoint[0]

    formatter = JsonFormatter()

    client = Client(
        server=args.server,
        email=args.email,
        password=args.password,
        azure_login=args.azure_login,
    )

    if args.action == "register":
        formatter.format(client.register(**args.data))
        return

    login_result = client.login()

    if args.action == "login":
        formatter.format(login_result)

    elif args.action == "list":
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
