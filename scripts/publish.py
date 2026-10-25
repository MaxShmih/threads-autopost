"""Публікує пости з черги, час яких настав.

Черга: queue/<YYYY-MM-DD>/<NN-slug>/post.json + картинка поруч.
Поля post.json: date, slot ("HH:MM", київський час), slug, topic, text, image, status.
Статуси: queued → published (або failed з полем error).

Threads обмежує один пост 500 символами, тому довгий текст ділиться
по абзацах: перша частина йде з картинкою, решта відповідями під нею.
"""
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import threads_api as api  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KYIV = ZoneInfo("Europe/Kyiv")
LIMIT = 500
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "2"))
DRY = os.environ.get("DRY_RUN") == "1"


def split_text(text: str, limit: int = LIMIT) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    pieces: list[str] = []
    for p in paras:
        if len(p) <= limit:
            pieces.append(p)
            continue
        cur = ""
        for s in re.split(r"(?<=[.!?…])\s+", p):
            if cur and len(cur) + 1 + len(s) > limit:
                pieces.append(cur)
                cur = s
            else:
                cur = f"{cur} {s}".strip()
        if cur:
            pieces.append(cur)
    chunks: list[str] = []
    cur = ""
    for p in pieces:
        cand = f"{cur}\n\n{p}" if cur else p
        if len(cand) <= limit:
            cur = cand
        else:
            if cur:
                chunks.append(cur)
            cur = p[:limit]
    if cur:
        chunks.append(cur)
    return chunks


def raw_url(path: Path) -> str:
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    rel = path.relative_to(ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}"


def wait_ready(container_id: str) -> None:
    for _ in range(12):
        st = api.get(container_id, fields="status,error_message")
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise api.ThreadsError(f"Контейнер {container_id}: {st}")
        time.sleep(5)
    raise api.ThreadsError(f"Контейнер {container_id} не готовий за 60 с")


def publish(uid: str, post: dict, folder: Path) -> dict:
    parts = split_text(post["text"])
    img = folder / post["image"]
    first = api.post(f"{uid}/threads", media_type="IMAGE", image_url=raw_url(img), text=parts[0])
    wait_ready(first["id"])
    root = api.post(f"{uid}/threads_publish", creation_id=first["id"])["id"]
    ids = [root]
    prev = root
    for part in parts[1:]:
        time.sleep(3)
        c = api.post(f"{uid}/threads", media_type="TEXT", text=part, reply_to_id=prev)
        wait_ready(c["id"])
        prev = api.post(f"{uid}/threads_publish", creation_id=c["id"])["id"]
        ids.append(prev)
    link = api.get(root, fields="permalink").get("permalink")
    return {"threads_id": root, "reply_ids": ids[1:], "permalink": link}


def main() -> int:
    now = dt.datetime.now(KYIV)
    due = []
    for f in sorted(ROOT.glob("queue/*/*/post.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        if p.get("status") != "queued":
            continue
        h, m = map(int, p["slot"].split(":"))
        when = dt.datetime.fromisoformat(p["date"]).replace(hour=h, minute=m, tzinfo=KYIV)
        if when <= now:
            due.append((when, f, p))
    due.sort(key=lambda x: x[0])
    if not due:
        print("Нічого публікувати.")
        return 0
    if not DRY and not os.environ.get("THREADS_TOKEN", "").strip():
        print(f"::warning::У черзі {len(due)} пост(ів), але секрет THREADS_TOKEN ще не заданий.")
        return 0
    uid = "me" if DRY else api.me()["id"]
    done = 0
    for when, f, p in due[:MAX_PER_RUN]:
        print(f"→ {p['date']} {p['slot']} {p['slug']}: {len(split_text(p['text']))} част.")
        if DRY:
            continue
        try:
            res = publish(uid, p, f.parent)
            p.update(res, status="published", published_at=dt.datetime.now(KYIV).isoformat(timespec="seconds"))
            p.pop("error", None)
            done += 1
            print(f"  опубліковано: {res.get('permalink')}")
        except api.ThreadsError as e:
            p["attempts"] = p.get("attempts", 0) + 1
            p["error"] = str(e)[:1000]
            if p["attempts"] >= 3:
                p["status"] = "failed"
            print(f"  помилка: {e}", file=sys.stderr)
        f.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        time.sleep(10)
    print(f"Опубліковано: {done}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
