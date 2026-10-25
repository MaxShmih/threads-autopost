"""Продовжує довготривалий токен Threads (діє 60 днів) і пише новий у файл для кроку gh secret set."""
import json
import os
import sys
import urllib.parse
import urllib.request

tok = os.environ.get("THREADS_TOKEN", "").strip()
if not tok:
    sys.exit("THREADS_TOKEN не заданий")
q = urllib.parse.urlencode({"grant_type": "th_refresh_token", "access_token": tok})
with urllib.request.urlopen(f"https://graph.threads.net/refresh_access_token?{q}", timeout=60) as r:
    data = json.loads(r.read().decode())
new = data.get("access_token")
if not new:
    sys.exit(f"Не вдалося оновити токен: {list(data)}")
print(f"::add-mask::{new}")
with open(os.environ.get("OUT", "new_token.txt"), "w") as fh:
    fh.write(new)
print(f"Токен оновлено, діє ще {int(data.get('expires_in', 0)) // 86400} дн.")
