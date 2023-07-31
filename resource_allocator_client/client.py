"""
Main Client class and Cache
"""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs
import webbrowser

import requests as req

logger = logging.getLogger(__name__)


class APIError(Exception):
    pass


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
        azure_login: bool = False,
    ):
        """
        Initialize the client. Either password or azure_login must be set

        Args:
            server: str: URL of the Resource Allocator server instance
            email: str: user's email for logging into the server
            password: str: user's password if using password authentication [default: None]
            azure_login: bool: whether to use Azure Active Directory Login [default: None]
        """
        if (
            ((password is None) & (not azure_login))
            | ((password is not None) & azure_login)
        ):
            raise ValueError("Either password or azure_login must be given")

        if (not server.startswith("http://")) or (server.startswith("https://")):
            server = f"https://{server}"

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
            try:
                content = result.json()
            except Exception:
                content = result.content

            message = (
                f"Request returned a non-ok exit status: {result.status_code}: "
                f"{content}"
            )
            raise APIError(message)

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
        result = self._make_request(method="GET", endpoint=endpoint)
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
        result = self._make_request(method="GET", endpoint=endpoint, id=id)
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
