"""Мінімальний клієнт Threads API без сторонніх залежностей."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://graph.threads.net/v1.0"


class ThreadsError(RuntimeError):
    pass


def token() -> str:
    t = os.environ.get("THREADS_TOKEN", "").strip()
    if not t:
        raise ThreadsError("Секрет THREADS_TOKEN не заданий у Settings → Secrets and variables → Actions.")
    return t


def _call(method: str, path: str, params: dict, retries: int = 2) -> dict:
    params = {**params, "access_token": token()}
    data = urllib.parse.urlencode(params).encode()
    url = f"{BASE}/{path.lstrip('/')}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}", method="GET")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code >= 500 and attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            raise ThreadsError(f"{method} {path} → HTTP {e.code}: {body}") from None
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            raise ThreadsError(f"{method} {path} → {e}") from None
    raise ThreadsError("unreachable")


def get(path: str, **params) -> dict:
    return _call("GET", path, params)


def post(path: str, **params) -> dict:
    return _call("POST", path, params)


def me() -> dict:
    return get("me", fields="id,username")
