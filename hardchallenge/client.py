"""Dependency-free client for the hard-challenge source service."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class RemoteChallengeError(RuntimeError):
    pass


class ChallengeClient:
    def __init__(self):
        self.host = settings.HARD_CHALLENGE_HOST.rstrip("/")

    def _get_json(self, path):
        request = Request(
            f"{self.host}/{path.lstrip('/')}", headers={"Accept": "application/json"}
        )
        try:
            with urlopen(request, timeout=settings.HARD_CHALLENGE_HTTP_TIMEOUT) as response:  # nosec B310
                payload = json.loads(response.read().decode(response.headers.get_content_charset() or "utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RemoteChallengeError(f"Could not load {path}: {exc}") from exc
        if payload.get("status") != 200 or not isinstance(payload.get("data"), list):
            raise RemoteChallengeError(f"{path} returned an unexpected response.")
        return payload

    def people(self):
        return self._get_json("people")["data"]

    def draft_batch(self, index):
        return self._get_json(f"draft/{index}")

    def fight_batch(self, index):
        return self._get_json(f"fight/{index}")
