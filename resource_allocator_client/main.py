"""
Resource Allocator Client

Command-line client to query the Resource-Allocator API application
"""

from abc import abstractmethod
from argparse import ArgumentParser
import base64
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


class Parser:
    #   Command subparsers
    _endpoint_kwargs = dict(
        dest="endpoint",
        choices=[
            "allocation",
            "auto_allocation",
            "images",
            "image_properties",
            "iterations",
            "requests",
            "resource_groups",
            "resource_to_group",
            "resources",
            "users",
        ],
    )
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

        #   Add separate subparsers
        _ = cls._add_register(subparsers)
        _ = cls._add_login(subparsers)
        _ = cls._add_list(subparsers)
        _ = cls._add_get(subparsers)
        _ = cls._add_create(subparsers)
        _ = cls._add_delete(subparsers)
        _ = cls._add_update(subparsers)
        _ = cls._add_query(subparsers)
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
    def _add_list(cls, subparsers: HasSubparsers) -> ArgumentParser:
        parser = subparsers.add_parser("list")
        parser.add_argument(**cls._endpoint_kwargs)
        return parser

    @classmethod
    def _add_get(cls, subparsers: HasSubparsers) -> ArgumentParser:
        parser = subparsers.add_parser("get")
        parser.add_argument(**cls._endpoint_kwargs)
        parser.add_argument(**cls._id_kwargs)
        return parser

    @classmethod
    def _add_create(cls, subparsers: HasSubparsers) -> ArgumentParser:
        parser = subparsers.add_parser("create")
        parser.add_argument(**cls._endpoint_kwargs)
        parser.add_argument(**cls._data_kwargs)
        return parser

    @classmethod
    def _add_delete(cls, subparsers: HasSubparsers) -> ArgumentParser:
        parser = subparsers.add_parser("delete")
        parser.add_argument(**cls._endpoint_kwargs)
        parser.add_argument(**cls._id_kwargs)
        return parser

    @classmethod
    def _add_update(cls, subparsers: HasSubparsers) -> ArgumentParser:
        parser = subparsers.add_parser("update")
        parser.add_argument(**cls._endpoint_kwargs)
        parser.add_argument(**cls._id_kwargs)
        parser.add_argument(**cls._data_kwargs)
        return parser

    @classmethod
    def _add_query(cls, subparsers: HasSubparsers) -> ArgumentParser:
        parser = subparsers.add_parser("query")
        parser.add_argument(**cls._endpoint_kwargs)
        parser.add_argument(**cls._data_kwargs)
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
    )

    if args.action == "register":
        formatter.format(client.register(**args.data))
        return

    #   Check odd args
    if "endpoint" in args and args.endpoint == "auto_allocation" and args.action != "create":
        raise ValueError("Endpoint auto_allocation is only valid for create action")

    login_result = client.login()

    if args.action == "login":
        result = login_result

    elif args.action == "list":
        result = client.list_items(endpoint=args.endpoint)

    elif args.action == "get":
        result = client.get(endpoint=args.endpoint, id=args.id)

    elif args.action == "query":
        result = client.query(endpoint=args.endpoint, **args.data)

    elif args.action == "create":
        if args.endpoint == "auto_allocation":
            args.endpoint = "allocation/automatic_allocation"
        result = client.create(endpoint=args.endpoint, **args.data)

    elif args.action == "delete":
        result = client.delete(endpoint=args.endpoint, id=args.id)

    elif args.action == "update":
        result = client.update(endpoint=args.endpoint, id=args.id, **args.data)

    else:
        raise ValueError(f"Invalid action: {args.action}")

    formatter.format(result)


if __name__ == "__main__":
    main()
