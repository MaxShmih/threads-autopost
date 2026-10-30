"""Обмінює код авторизації Threads на довготривалий токен (60 днів).

Потрібні змінні: THREADS_APP_ID, THREADS_APP_SECRET, REDIRECT_URI, CODE, OUT.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def call(url: str, data: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')}")


env = {k: os.environ.get(k, "").strip() for k in ("THREADS_APP_ID", "THREADS_APP_SECRET", "REDIRECT_URI", "CODE")}
missing = [k for k, v in env.items() if not v]
if missing:
    sys.exit(f"Не задано: {', '.join(missing)}")

code = env["CODE"].split("#")[0]  # Threads додає «#_» у кінці коду
short = call("https://graph.threads.net/oauth/access_token", {
    "client_id": env["THREADS_APP_ID"],
    "client_secret": env["THREADS_APP_SECRET"],
    "grant_type": "authorization_code",
    "redirect_uri": env["REDIRECT_URI"],
    "code": code,
})
if "access_token" not in short:
    sys.exit(f"Не вдалося отримати короткий токен: {list(short)}")
print(f"::add-mask::{short['access_token']}")

q = urllib.parse.urlencode({
    "grant_type": "th_exchange_token",
    "client_secret": env["THREADS_APP_SECRET"],
    "access_token": short["access_token"],
})
long = call(f"https://graph.threads.net/access_token?{q}")
tok = long.get("access_token")
if not tok:
    sys.exit(f"Не вдалося отримати довгий токен: {list(long)}")
print(f"::add-mask::{tok}")
with open(os.environ.get("OUT", "token.txt"), "w") as fh:
    fh.write(tok)

me = call(f"https://graph.threads.net/v1.0/me?fields=username&access_token={urllib.parse.quote(tok)}")
print(f"Готово: токен для @{me.get('username', '?')}, діє {int(long.get('expires_in', 0)) // 86400} дн.")
