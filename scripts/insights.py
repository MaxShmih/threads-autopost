"""Збирає статистику опублікованих постів за останні 30 днів і записує в post.json."""
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import threads_api as api  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KYIV = ZoneInfo("Europe/Kyiv")
METRICS = "views,likes,replies,reposts,quotes,shares"


def value(item: dict):
    if "total_value" in item:
        return item["total_value"].get("value")
    vals = item.get("values") or []
    return vals[-1].get("value") if vals else None


def main() -> int:
    now = dt.datetime.now(KYIV)
    cutoff = now - dt.timedelta(days=30)
    rows = []
    for f in sorted(ROOT.glob("queue/*/*/post.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        if p.get("status") != "published" or not p.get("threads_id"):
            continue
        pub = dt.datetime.fromisoformat(p["published_at"])
        if pub < cutoff:
            continue
        try:
            data = api.get(f"{p['threads_id']}/insights", metric=METRICS).get("data", [])
            p["stats"] = {d["name"]: value(d) for d in data}
            p["stats_at"] = now.isoformat(timespec="seconds")
            f.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            rows.append({"date": p["date"], "slug": p["slug"], "topic": p.get("topic"), **p["stats"]})
            print(f"{p['date']} {p['slug']}: {p['stats']}")
        except api.ThreadsError as e:
            print(f"{p['slug']}: {e}", file=sys.stderr)
    out = ROOT / "stats" / "latest.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"updated": now.isoformat(timespec="seconds"), "posts": rows},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
