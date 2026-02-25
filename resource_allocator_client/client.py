"""
Main Client class and Cache
"""

from dataclasses import dataclass
import datetime as dt
import json
import logging
from pathlib import Path
import re
from typing import Any
import webbrowser

import requests as req

from resource_allocator_client.callback import run_callback_server

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
    email: str
    token: str = None
    expires_at: dt.datetime = None
    path: Path = None

    @staticmethod
    def _replace_chars(value: str) -> str:
        chars = re.escape(r'<>:/\|?*')
        pattern = f"[{chars}]+"
        result = re.sub(pattern, "_", value)
        return result

    def __post_init__(self):
        if not self.path:
            self.path = Path(".") / (self._replace_chars(self.server) + ".json")
        elif isinstance(self.path, str):
            self.path = Path(self.path)

        self.path = self.path.parent / self._replace_chars(self.path.name)

    def read(self):
        path = self.path
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as cur_path:
            try:
                data = json.load(cur_path)
            except Exception as e:
                logger.error(f"Could not read cache: {e}")

        expires_at = dt.datetime.fromisoformat(data["expires_at"])
        if (
            self.server == data["server"]
            and self.email == data["email"]
            and expires_at > dt.datetime.now(tz=dt.timezone.utc)
        ):
            self.token = data["token"]
            self.expires_at = expires_at
        else:
            logger.info("Existing token expired or invalid")

    def write(self):
        with open(self.path, "w", encoding="utf-8") as cur_file:
            data = self.__dict__.copy()
            data["path"] = str(data["path"])
            data["expires_at"] = data["expires_at"].isoformat()
            json.dump(data, cur_file)

    def update_from_login(self, data: dict):
        self.expires_at = (
            dt.datetime.fromisoformat(data["expires_at"])
            if "expires_at" in data and data.get("expires_at")
            else dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(hours=1)
        )
        self.token = data["token"]
        self.write()


class Client:
    """
    Resource Allocator Client class to handle all API operations
    """

    redirect_hostname = "localhost"
    redirect_port = 8080

    def __init__(
        self,
        server: str,
        email: str,
        password: str | None = None,
        azure_login: bool = False,
        cache_path: str | None = None,
        request_timeout: int = 10
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

        if (not server.startswith("http://")) and (not server.startswith("https://")):
            server = f"https://{server}"

        self.server = server.rstrip("/")
        self.email = email
        self.password = password
        self.azure_login = azure_login
        self.cache = Cache(server=self.server, email=email, path=cache_path)
        self.request_timeout = request_timeout

    def _make_request(
        self,
        method: str,
        endpoint: str,
        id: int | None = None,
        params: dict | None = None,
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
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cache.token}",
            },
            params=params,
            json=data,
            timeout=self.request_timeout,
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

    def register(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Register in a server using email-password login OR Azure Active Directory login

        Args:
            data: keyword arguments to pass on

        Returns:
            dict[str, Any]: API response
        """
        if self.azure_login:
            result = self._register_azure()
        else:
            result = self._register_email(first_name=first_name, last_name=last_name)

        self.cache.update_from_login(result)

    def _register_azure(self, **data) -> dict[str, Any]:
        raise NotImplementedError()

    def _register_email(self, first_name: str, last_name: str) -> dict[str, Any]:
        if not first_name or not last_name:
            raise ValueError("Email registration requires first_name and last_name")

        result = self._make_request(
            method="POST",
            endpoint="register",
            email=self.email,
            password=self.password,
            first_name=first_name,
            last_name=last_name,
        )
        if "token" not in result:
            logger.error("Bad register result")
            return result

        return result

    def login(self) -> dict[str, Any]:
        """
        Log into an instance using email-password login or Azure Active Directory login

        Args:
            None

        Returns:
            dict[str, Any]: API response
        """
        #   Try reading the cache
        self.cache.read()
        if self.cache.token:
            logger.info("Using valid cache")
            return

        if self.azure_login:
            result = self._login_azure()
        else:
            result = self._login_email(email=self.email, password=self.password)

        if not isinstance(result, dict) or "token" not in result:
            raise APIError(f"Invalid login response: {result}")

        self.cache.update_from_login(result)

    def _login_azure(self):
        #   Get auth URL and redirect
        redirect_uri = f"http://{self.redirect_hostname}:{self.redirect_port}"
        login_init = self._make_request(
            method="GET",
            endpoint="login_azure",
            params={"redirect_uri": redirect_uri},
        )
        auth_url = login_init["auth_url"]

        #   Ask user to paste the redirect
        if not webbrowser.open(auth_url):
            print(f"Please visit the following URL: {auth_url}")

        code = run_callback_server(hostname=self.redirect_hostname, port=self.redirect_port)

        login_finish = self._make_request(
            method="POST",
            endpoint="login_azure",
            code=code,
            email=self.email,
            redirect_uri=redirect_uri,
        )
        return login_finish

    def _login_email(self, email: str, password: str) -> dict[str, Any]:
        result = self._make_request(
            method="POST",
            endpoint="login",
            email=email,
            password=password,
        )
        return result

    @staticmethod
    def _paginate(
        limit: int,
        offset: int,
        order_by: list[str],
    ) -> dict:
        params = {
            "limit": limit,
            "offset": offset,
            "order_by": order_by,
        }
        if order_by:
            params["order_by"] = order_by

        return params

    def list_items(
        self,
        endpoint: str,
        limit: int,
        offset: int,
        order_by: list[str],
        **data,
    ) -> list[dict[str, Any]]:
        """
        List items from an API endpoint with optional search terms. Search is handled client-side at
        the moment.

        Args:
            endpoint: str: address of the API endpoint
            limit: int: number of items to return
            offset: int: query offset
            order_by: list[str]: Comma-separated list of columns to order the result. Mark
                descending by "-field"
            data: dict: key-value pairs to query against. Return results only if all columns in the
                given data object are equal to the respective columns of the object

        Returns:
            list[dict[str, Any]]: API response
        """
        result = self._make_request(
            method="GET",
            endpoint=endpoint,
            params=self._paginate(limit=limit, offset=offset, order_by=order_by),
        )
        if data:
            result = [
                item
                for item
                in result
                if all((
                    str(item.get(key)).casefold() == str(value).casefold()
                    for key, value in data.items()
                ))
            ]
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

    def create(self, endpoint: str, **data) -> dict[str, Any]:
        """
        Create an item for an API endpoint

        Args:
            endpoint: str: address of the API endpoint
            data: dict: key-value pairs of data for the created object

        Returns:
            dict[str, Any]: API response
        """
        # query_result = self.query(endpoint=endpoint, **data)
        # if query_result:
        #     return query_result[0]

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
