import logging
import time
from typing import Any, Self

import httpx

logger = logging.getLogger(__name__)

_RATE_LIMIT_INTERVAL = 1.0
_RATE_LIMIT_COOLDOWN = 60.0
_MAX_PAGE_SIZE = 300
_MAX_429_RETRIES = 1

_STRING_FIELDS = frozenset({"gasDayStart", "name", "code", "url", "info", "status"})


class GIEApiError(Exception):
    status_code: int | None

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GIEClient:
    _base_url: str
    _api_key: str
    _timeout: float

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.Client | None = None
        self._last_request_time: float = 0.0

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                headers={"x-key": self._api_key},
                timeout=self._timeout,
                follow_redirects=True,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < _RATE_LIMIT_INTERVAL:
            sleep_time = _RATE_LIMIT_INTERVAL - elapsed
            logger.debug("Rate limit: sleeping %.2fs", sleep_time)
            time.sleep(sleep_time)

    def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> httpx.Response:
        retries = 0
        while True:
            self._wait_for_rate_limit()
            try:
                response = self.client.get(endpoint, params=params)
                self._last_request_time = time.monotonic()
            except httpx.RequestError as exc:
                raise GIEApiError(f"Request failed: {exc}") from exc

            if response.status_code == 429:
                if retries < _MAX_429_RETRIES:
                    retries += 1
                    logger.warning("429 rate limited, sleeping %ds before retry", _RATE_LIMIT_COOLDOWN)
                    time.sleep(_RATE_LIMIT_COOLDOWN)
                    continue
                raise GIEApiError("Rate limited (429) after retry", status_code=429)

            if response.status_code >= 400:
                raise GIEApiError(
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    status_code=response.status_code,
                )
            return response

    def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Fetch endpoint and return raw parsed JSON (for non-standard responses like listings)."""
        response = self._request(endpoint, params)
        try:
            return response.json()
        except Exception as exc:
            raise GIEApiError(f"Malformed JSON response: {exc}") from exc

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        response = self._request(endpoint, params)
        try:
            body = response.json()
        except Exception as exc:
            raise GIEApiError(f"Malformed JSON response: {exc}") from exc
        data: list[dict[str, Any]] = body.get("data", [])
        return [_parse_floats(record) for record in data]

    def get_all(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = dict(params) if params else {}
        params["size"] = str(_MAX_PAGE_SIZE)
        page = 1
        all_data: list[dict[str, Any]] = []

        while True:
            params["page"] = str(page)
            response = self._request(endpoint, params)
            try:
                body = response.json()
            except Exception as exc:
                raise GIEApiError(f"Malformed JSON response: {exc}") from exc

            data: list[dict[str, Any]] = body.get("data", [])
            all_data.extend(_parse_floats(record) for record in data)

            last_page = int(body.get("last_page", 1))
            if page >= last_page:
                break
            page += 1

        return all_data


def _parse_floats(record: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in record.items():
        if key in _STRING_FIELDS or not isinstance(value, str):
            parsed[key] = value
            continue
        if value == "" or value == "-":
            parsed[key] = None
            continue
        try:
            parsed[key] = float(value)
        except ValueError:
            parsed[key] = value
    return parsed
