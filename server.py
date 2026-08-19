#!/usr/bin/env python3
"""Live board server for the Wideout Board.

Serves index.html and a /api/board endpoint that pulls the week's receiving
lines from ESPN. The browser can't call ESPN from a hosted page (CSP) and
shouldn't hammer it from every open tab either, so the fetching happens here,
once, behind a short cache.

    python3 server.py [--port 8765] [--week 3]

The roster is read straight out of index.html so there is exactly one copy of
it; edit the ROSTER array there and the server picks the change up on reload.
"""

import argparse
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
INDEX = ROOT / "index.html"
ESPN = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl"
CACHE_SECONDS = 20
UA = {"User-Agent": "Mozilla/5.0 (wideout-board)"}


def norm(name):
    """Match names the way the page does: ignore case, punctuation, spacing."""
    s = name.lower().replace("'", "").replace("’", "")
    s = s.replace(".", "").replace("-", " ")
    return " ".join(s.split())


ENTRY = re.compile(
    r'\{\s*manager:\s*"(?P<manager>[^"]+)",\s*'
    r'wr:\s*"(?P<wr>[^"]+)",\s*'
    r'names:\s*(?P<names>\[[^\]]*\]),\s*'
    r'team:\s*"(?P<team>[^"]+)",\s*'
    r'game:\s*"(?P<game>[^"]+)",\s*'
    r'kickoff:\s*"(?P<kickoff>[^"]+)"\s*\}',
    re.S,
)


def load_roster():
    """Pull the ROSTER array out of index.html — one source of truth."""
    html = INDEX.read_text()
    try:
        block = html[html.index("const ROSTER = ["):html.index("].map(r =>")]
    except ValueError:
        raise SystemExit("could not find the ROSTER array in index.html")
    rows = [m.groupdict() for m in ENTRY.finditer(block)]
    for r in rows:
        r["names"] = json.loads(r["names"])
    if not rows:
        raise SystemExit("ROSTER array in index.html parsed as empty")
    return rows


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def build_board(week):
    """Fetch the week and fold it onto the roster."""
    roster = load_roster()
    board = get_json(f"{ESPN}/scoreboard?seasontype=1&week={week}&dates=2026")
    events = board.get("events", [])
    if not events:
        raise RuntimeError(f"scoreboard returned no games for week {week}")

    # Only the games with one of our receivers matter, and a game that has not
    # kicked off has no box score to read — so skip both rather than pulling all
    # sixteen summaries on every refresh.
    our_teams = {entry["team"] for entry in roster}
    lines, team_state, needed = {}, {}, []
    for event in events:
        competition = (event.get("competitions") or [{}])[0]
        sides = competition.get("competitors") or []
        names = [(c.get("team") or {}).get("displayName") for c in sides]
        names = [n for n in names if n]
        if not any(n in our_teams for n in names):
            continue

        status = (event.get("status") or {}).get("type") or {}
        label = " @ ".join(
            (c.get("team") or {}).get("abbreviation", "?") for c in reversed(sides)
        ) or None
        state = {
            "state": status.get("state", "pre"),
            "detail": status.get("shortDetail", ""),
            "game": label,
        }
        for n in names:
            if n in our_teams:
                team_state[n] = state
        if state["state"] != "pre":
            needed.append(event["id"])

    for event_id in needed:
        try:
            summary = get_json(f"{ESPN}/summary?event={event_id}")
        except (urllib.error.URLError, ValueError):
            continue
        for side in (summary.get("boxscore") or {}).get("players", []):
            team_name = (side.get("team") or {}).get("displayName")
            for cat in side.get("statistics", []):
                if cat.get("name") != "receiving":
                    continue
                for athlete in cat.get("athletes", []):
                    display = (athlete.get("athlete") or {}).get("displayName")
                    if not display:
                        continue
                    stats = athlete.get("stats") or []

                    def num(i):
                        try:
                            return int(stats[i])
                        except (IndexError, ValueError):
                            return 0

                    lines[norm(display)] = {
                        "team": team_name,
                        "rec": num(0), "yds": num(1),
                        "td": num(3), "lng": num(4), "tgt": num(5),
                    }

    rows = []
    for entry in roster:
        ts = team_state.get(entry["team"], {})
        row = {
            "manager": entry["manager"], "wr": entry["wr"],
            "team": entry["team"], "kickoff": entry["kickoff"],
            "game": ts.get("game") or entry["game"],
            "state": ts.get("state", "pre"), "detail": ts.get("detail", ""),
            "played": False,
            "yds": None, "rec": None, "td": None, "lng": None, "tgt": None,
        }
        for candidate in entry["names"]:
            hit = lines.get(norm(candidate))
            if hit:
                row.update(hit)
                row["played"] = True
                break
        rows.append(row)

    return {
        "week": week,
        "updated": time.time(),
        "allFinal": all(r["state"] == "post" for r in rows),
        "rows": rows,
    }


class Board:
    """Short-cached board, so N open tabs are still one ESPN fetch."""

    def __init__(self, week):
        self.week = week
        self.lock = threading.Lock()
        self.payload = None
        self.fetched_at = 0.0
        self.error = None

    def get(self):
        with self.lock:
            fresh = time.time() - self.fetched_at < CACHE_SECONDS
            if self.payload and fresh:
                return self.payload, self.error
            try:
                self.payload = build_board(self.week)
                self.fetched_at = time.time()
                self.error = None
            except Exception as exc:  # serve stale data rather than nothing
                self.error = str(exc)
                if self.payload is None:
                    raise
            return self.payload, self.error


class Handler(BaseHTTPRequestHandler):
    board = None
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            try:
                self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            except OSError:
                self._send(404, b"index.html not found", "text/plain")
            return

        if path == "/api/board":
            try:
                payload, error = self.board.get()
            except Exception as exc:
                body = json.dumps({"error": str(exc)}).encode()
                self._send(502, body, "application/json")
                return
            payload = dict(payload, stale=bool(error))
            if error:
                payload["error"] = error
            self._send(200, json.dumps(payload).encode(), "application/json")
            return

        self._send(404, b"not found", "text/plain")

    def log_message(self, fmt, *args):
        if "/api/board" in (args[0] if args else ""):
            sys.stderr.write(f"  {self.address_string()} {fmt % args}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--week", type=int, default=3)
    args = ap.parse_args()

    Handler.board = Board(args.week)
    roster = load_roster()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"Wideout Board — preseason week {args.week}, {len(roster)} managers")
    print(f"  http://localhost:{args.port}")
    print("  anyone on your network can use your LAN address on the same port")
    print("  ctrl-c to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        server.server_close()


if __name__ == "__main__":
    main()
