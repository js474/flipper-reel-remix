"""Tagesplanung der Remix-Trial-Reels (Lanes-Modell).

Jede Lane ist ein Inhalt (ein Original-Reel) mit einer Warteschlange gerenderter Varianten.
Pro Tag bekommt jede Lane höchstens einen Slot. Damit läuft ein Inhalt nie zweimal am selben Tag.

Befehle:
  python3 plan.py day 2026-11-14 [--exclude bad,kann]   Posts für den Tag als JSON (ändert nichts)
  python3 plan.py commit 2026-11-14 <content> <V> <metricool_id> <slot>
  python3 plan.py status                                 Lanes, Restvarianten, freie Lanes
  python3 plan.py add-lane lane.json                     neue Lane aus Render-Ergebnis anlegen
  python3 plan.py done-lanes                             Lanes ohne Varianten, deren Repost fehlt
  python3 plan.py set-repost <content> <YYYY-MM-DD> <winner V>
  python3 plan.py result <content> <V> <views> <shares> <saves> <skip>
"""
import datetime as dt, json, re, sys

STATE = "state.json"
VORHER = ("V6", "V7", "V8")


def load():
    return json.load(open(STATE, encoding="utf-8"))


def save(s):
    json.dump(s, open(STATE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(STATE, "a").write("\n")


DOMAIN = re.compile(r"\s*(oder\s+)?(auf\s+)?(?<![@\w.])(https?://)?(www\.)?[a-z0-9-]+\.(de|com|net|immo|io|shop)\b(/\S*)?", re.I)


def clean_caption(text):
    """Keine Links oder Domains in Instagram-Captions."""
    out = []
    for line in text.split("\n"):
        new = DOMAIN.sub("", line).rstrip()
        new = re.sub(r"\s+(🫶)", r"\1", new)
        if new != line.rstrip() and not re.search(r"[A-Za-zÄÖÜäöüß0-9]", new):
            continue
        out.append(new)
    return "\n".join(out)


def caption_for(lane, v):
    body = lane["caption"]
    hooks = lane.get("hooks") or []
    first = lane.get("hook_line", "")
    if v in VORHER and VORHER.index(v) < len(hooks):
        first = hooks[VORHER.index(v)]
    text = (first + "\n\n" + body) if first else body
    return clean_caption(text)


def day(date, exclude):
    s = load()
    slots = s["slots"]["remix"]
    d = dt.date.fromisoformat(date)
    used = {p["content"] for p in s["posted"] if p["date"] == date}
    active = [l for l in s["lanes"] if l["queue"] and l["content"] not in exclude
              and date not in l.get("block", []) and l["content"] not in used
              and l.get("start", "0000") <= date]
    taken = {p["slot"] for p in s["posted"] if p["date"] == date}
    off = d.toordinal() % len(slots)
    order = [x for x in slots[off:] + slots[:off] if x not in taken]
    plan = []
    for lane, slot in zip(sorted(active, key=lambda l: l["lane"]), order):
        item = lane["queue"][0]
        plan.append({"date": date, "slot": slot, "content": lane["content"], "shortcode": lane["shortcode"],
                     "variant": item["v"], "media": item["url"], "caption": caption_for(lane, item["v"]),
                     "existing": item.get("existing")})
    plan.sort(key=lambda p: p["slot"])
    print(json.dumps(plan, ensure_ascii=False, indent=1))


def commit(date, content, v, mid, slot=None):
    s = load()
    lane = next(l for l in s["lanes"] if l["content"] == content)
    item = next(q for q in lane["queue"] if q["v"] == v)
    if any(p["date"] == date and p["content"] == content for p in s["posted"]):
        sys.exit(f"ABBRUCH: {content} ist am {date} schon geplant")
    lane["queue"].remove(item)
    s["posted"].append({"date": date, "slot": slot, "content": content, "shortcode": lane["shortcode"],
                        "variant": v, "metricool_id": mid, "media": item["url"]})
    lane.setdefault("trial_days", []).append(date)
    save(s)
    print(f"ok {date} {content} {v} {mid}")


def status():
    s = load()
    for l in s["lanes"]:
        print(f"Lane {l['lane']}: {l['content']:<12} rest {len(l['queue']):>2} {[q['v'] for q in l['queue']]} "
              f"repost {l.get('repost')}")
    free = len(s["slots"]["remix"]) - sum(1 for l in s["lanes"] if l["queue"])
    print(f"Freie Lanes (brauchen neues Reel): {max(free, 0)}")


def add_lane(path):
    s = load()
    new = json.load(open(path, encoding="utf-8"))
    if any(l["content"] == new["content"] for l in s["lanes"] if l["queue"]):
        sys.exit(f"ABBRUCH: Lane {new['content']} läuft noch")
    used = {l["lane"] for l in s["lanes"] if l["queue"]}
    new["lane"] = min(set(range(1, len(s["slots"]["remix"]) + 1)) - used)
    s["lanes"] = [l for l in s["lanes"] if not (l["lane"] == new["lane"] and not l["queue"] and l.get("repost"))]
    s["lanes"].append(new)
    save(s)
    print(f"Lane {new['lane']} angelegt: {new['content']} mit {len(new['queue'])} Varianten")


def done_lanes():
    s = load()
    out = [{"content": l["content"], "shortcode": l["shortcode"], "last_trial": max(l.get("trial_days", ["-"])),
            "trials": [p for p in s["posted"] if p["content"] == l["content"]]}
           for l in s["lanes"] if not l["queue"] and not l.get("repost")]
    print(json.dumps(out, ensure_ascii=False, indent=1))


def set_repost(content, date, winner):
    s = load()
    for l in s["lanes"]:
        if l["content"] == content:
            l["repost"] = date
            l["winner"] = winner
    s.setdefault("variant_wins", {})
    s["variant_wins"][winner] = s["variant_wins"].get(winner, 0) + 1
    save(s)
    print("ok")


def result(content, v, views, shares, saves, skip):
    s = load()
    s.setdefault("results", []).append({"content": content, "variant": v, "views": int(views),
                                        "shares": int(shares), "saves": int(saves), "skip": float(skip)})
    save(s)
    print("ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "day":
        ex = a[a.index("--exclude") + 1].split(",") if "--exclude" in a else []
        day(a[1], [e for e in ex if e])
    elif a[0] == "commit":
        commit(a[1], a[2], a[3], a[4], a[5] if len(a) > 5 else None)
    elif a[0] == "status":
        status()
    elif a[0] == "add-lane":
        add_lane(a[1])
    elif a[0] == "done-lanes":
        done_lanes()
    elif a[0] == "set-repost":
        set_repost(a[1], a[2], a[3])
    elif a[0] == "result":
        result(*a[1:7])
