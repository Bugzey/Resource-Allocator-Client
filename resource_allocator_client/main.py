"""
Resource Allocator Client

Command-line client to query the Resource-Allocator API application
"""

from abc import abstractmethod
from argparse import ArgumentParser
import base64
from dataclasses import dataclass
from getpass import getpass
import json
import logging

from resource_allocator_client.client import Client

logger = logging.getLogger(__name__)


class Formatter:
    """
    Base class to format output
    """
    @abstractmethod
    def format(self, output: dict) -> None: ...


class JsonFormatter(Formatter):
    """
    Formatter-subclass to format and print API responses in JSON format
    """
    def format(self, output: dict) -> None:
        print(json.dumps(output, indent=2))


class HasSubparsers:
    """
    Typing helper
    """
    def add_parser(self) -> ArgumentParser: ...


@dataclass
class Action:
    """
    Define an action that can be performed on a resource
    """
    name: str
    method: str
    endpoint: str | None = None
    prepend_id: bool = False
    resource: "Resource" = None

    def __str__(self):
        return self.name


@dataclass
class Resource:
    """
    Define a resource of the API
    """
    name: str
    actions: list[Action]
    endpoint: str | None = None

    def __post_init__(self):
        self.endpoint = self.endpoint or self.name
        for action in self.actions:
            action.resource = self


def crud_actions() -> list[Action]:
    result = [
        Action("create", "POST", prepend_id=False),
        Action("get", "GET", prepend_id=True),
        Action("list", "GET", prepend_id=False),
        Action("query", "GET", prepend_id=False),
        Action("update", "PUT", prepend_id=True),
        Action("delete", "DELETE", prepend_id=True),
    ]
    return result


class Parser:
    #   Command subparsers
    _resources = [
        Resource("allocations", endpoint="allocation", actions=[
            *crud_actions(),
            Action("auto_allocation", method="POST", endpoint="auto_allocation", prepend_id=True),
        ]),
        Resource("images", actions=crud_actions()),
        Resource("image_properties", actions=crud_actions()),
        Resource("iterations", actions=crud_actions()),
        Resource("requests", actions=crud_actions()),
        Resource("resource_groups", actions=crud_actions()),
        Resource("resource_to_group", actions=crud_actions()),
        Resource("resources", actions=crud_actions()),
        Resource("users", actions=[
            *crud_actions(),
            Action(name="me", method="GET", endpoint="me", prepend_id=False),
        ]),
    ]
    _data_kwargs = dict(
        dest="data",
        nargs="*",
        metavar="KEY=VALUE",
        help="Key-value pairs to create, update or query",
    )
    _id_kwargs = dict(dest="id", help="ID of the item")

    @classmethod
    def make_parser(cls) -> ArgumentParser:
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
        parser.add_argument("-t", "--timeout", type=int, help="Request timeout", default=10)

        #   Auth group
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-p",
            "--password",
            help="User password. Leave blank for interactive entry",
        )
        group.add_argument("-a", "--azure-login", action="store_true", help="Log-in via Azure AD")
        parser.add_argument("-c", "--cache", help="Path to a custom login cache file")

        subparsers = parser.add_subparsers(
            title="subcommands",
            dest="action",
            required=True,
        )
        cls._add_register(subparsers)
        cls._add_login(subparsers)

        #   Add separate subparsers
        for resource in cls._resources:
            _ = cls._add_resource(subparsers, resource)

        return parser

    @classmethod
    def _add_register(cls, subparsers: HasSubparsers) -> ArgumentParser:
        parser = subparsers.add_parser("register")
        parser.add_argument(**cls._data_kwargs)
        return parser

    @classmethod
    def _add_login(cls, subparsers: HasSubparsers) -> ArgumentParser:
        parser = subparsers.add_parser("login")
        return parser

    @classmethod
    def _add_resource(cls, subparsers: HasSubparsers, resource: Resource) -> ArgumentParser:
        parser = subparsers.add_parser(resource.name)
        parser.resource = resource
        parser.add_argument(
            dest="action",
            choices=resource.actions,
            type=lambda x: next(item for item in resource.actions if item.name == x),
        )
        parser = cls._add_list_options(parser)
        parser.add_argument(**cls._data_kwargs)
        parser.add_argument("--id", help="Resource identifier if needed", type=int)
        return parser

    @classmethod
    def _add_list_options(cls, parser: ArgumentParser) -> ArgumentParser:
        parser.add_argument(
            "-l",
            "--limit",
            type=int,
            help="Number of items to return",
            default=200,
        )
        parser.add_argument(
            "-o",
            "--offset",
            type=int,
            help="Offset total result set",
            default=0,
        )
        parser.add_argument(
            "--order-by",
            type=lambda x: str(x).split(","),
            help=(
                "Comma-separated list of columns to order the result set by. Add '-' in front of a "
                "colum name for descending order"
            ),
        )
        return parser

    @classmethod
    def parse_data_args(cls, args: list[str]) -> dict[str, str]:
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

            key, value = item.split("=", maxsplit=1)
            key = key.strip()
            value = value.strip()

            if value.casefold() in ("yes", "true"):
                value = True
            elif value.casefold() in ("no", "false"):
                value = False
            elif value.isnumeric():
                value = int(value)
            elif "=" in value:
                value = cls.parse_data_args(value.split(","))
            elif key == "image":
                with open(value, "rb") as cur_file:
                    value = cur_file.read()
                    value = base64.b64encode(value).decode("utf-8")

            result[key] = value

        return result


def main() -> None:
    """
    Module's main function that is run whenever the module is run on its own from the command line

    Args:
        None

    Returns:
        None
    """
    parser_factory = Parser()
    parser = parser_factory.make_parser()
    args = parser.parse_args()
    if not args.password and not args.azure_login:
        args.password = getpass(f"Password for {args.email}: ")

    #   Postprocess args
    if "data" in dir(args):
        args.data = parser_factory.parse_data_args(args.data)

    formatter = JsonFormatter()

    client = Client(
        server=args.server,
        email=args.email,
        password=args.password,
        azure_login=args.azure_login,
        cache_path=args.cache,
        request_timeout=args.timeout,
    )

    if args.action == "register":
        formatter.format(client.register(**args.data))
        return

    login_result = client.login()

    if args.action == "login":
        result = login_result

    #   Extract resource and action from argument parsing
    action: Action = args.action
    resource: Resource = action.resource

    result = client._make_request(
        method=action.method,
        endpoint=resource.endpoint,
        id=args.id,
        params={"limit": args.limit, "offset": args.offset, "order_by": args.order_by},
        data=args.data
    )
    formatter.format(result)
    return


if __name__ == "__main__":
    main()
