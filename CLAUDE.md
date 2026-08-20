# Fantasy Draft Order Tracker

## What this is
Our league is deciding **2026 draft order** with a preseason gimmick: each manager
called one NFL wide receiver. Whoever's receiver puts up the most **receiving yards
in Preseason Week 3** gets the earliest pick — **most yards = pick #1**, down to the
fewest picking last.

## Which week (this matters — it was wrong once)
The contest runs on **Preseason Week 3: 20–23 August 2026**, which was still
upcoming when the tracker was built. Week 2 (13–15 August) is a *finished* week and
is NOT the contest — an early version of this dashboard was built against Week 2 by
mistake because the roster message was labelled "week 2". If a future week is ever
in doubt, check `status.type.description` on the ESPN scoreboard: the contest week
should read `Scheduled`, not `Final`.

## Roster — Preseason Week 3, 2026
| Manager | WR | NFL team | Game | Kickoff (UTC) |
|---|---|---|---|---|
| Matthew Jin | Caleb Douglas | Miami Dolphins | NYG @ MIA | 2026-08-22 20:00 |
| Matthew Tam | Ja'Kobi Lane | Baltimore Ravens | BAL @ MIN | 2026-08-22 17:00 |
| David | Omar Cooper Jr. | New York Jets | NYJ @ PIT | 2026-08-21 23:00 |
| Owen | Germie Bernard | Pittsburgh Steelers | NYJ @ PIT | 2026-08-21 23:00 |
| Xuanzhi | Kaden Wetjen | Pittsburgh Steelers | NYJ @ PIT | 2026-08-21 23:00 |
| Luke Gailloux | Bryce Lance | New Orleans Saints | NO @ LAR | 2026-08-22 20:00 |
| Albert | Zach Branch | Atlanta Falcons | ATL @ IND | 2026-08-22 17:00 |
| Taisei | De'Zhaun Stribling | San Francisco 49ers | SF @ LAC | 2026-08-21 02:00 |
| Chris | KC Concepcion | Cleveland Browns | BUF @ CLE | 2026-08-22 17:00 |
| Alexandre | Malachi Fields | New York Giants | NYG @ MIA | 2026-08-22 20:00 |

Ten managers. David, Owen and Xuanzhi share NYJ @ PIT; Matthew Jin and Alexandre are
head-to-head in NYG @ MIA.

**Adding a manager:** append to the `ROSTER` array in `index.html` (the server parses
it from there) and give them the next `--sN` colour. The palette carries ten
validated slots; an eleventh needs a new hue validated with the data-viz skill's
`validate_palette.js` against the existing nine, in **both** modes — do not eyeball
it. The first attempt at a ninth colour, a brown, failed on chroma and sat ΔE 5.1
from slot-8 red under protanopia; teal passed everything.

## House rules (settled)
- **An inactive receiver scores 0.** No line in a *final* box score is a zero and is
  ranked as one. Before kickoff there is still no figure — the code keeps those
  distinct: the zero is only applied once the game's state is `post`.
- **Tie-breaks**, in order: PPR points → longest reception → points scored by his
  offense → total offense yards. These are **not implemented**; the board ranks on
  receiving yards alone and the league settles ties by hand from the box scores.
  They are printed at the foot of the page for reference.

## Requirements
- Single-file HTML dashboard (`index.html`) — no build step, no server. Opens by
  double-clicking, and publishes as a Claude Artifact for the league to view.
- Pre-game is the *normal* state, not an error: rows start empty, sorted by
  kickoff, and **no pick number is shown until a figure decides it** (an undecided
  slot renders `—`, never a provisional rank).
- Distinguish three empty states, because they mean different things:
  `Scheduled` (not played yet) → `—`; `Final` with no receiving line
  (played, no catches) → `0`; and a manual figure, which always wins.
- Pulls live from ESPN's public site API (no key): `/scoreboard?seasontype=1&week=3`
  for game state, then `/summary?event=<id>` per game for receiving lines.
- Per-row manual override, saved to `localStorage`, always beating the fetched value.
- Both light and dark themes, defined token-level on `:root` so `body` can see them.

## Running it live (`server.py`)
`python3 server.py` (stdlib only, no dependencies) serves the board at
<http://localhost:8765> and exposes `/api/board`, which fetches the week from ESPN
and folds it onto the roster. Flags: `--port`, `--week`.

- The **roster is parsed straight out of `index.html`** so there is only ever one
  copy of it. Edit the `ROSTER` array there; the server re-reads on each request.
- Responses are cached for 20 seconds, so many open tabs are still one ESPN fetch.
- If ESPN fails, the last good payload is served with `stale: true` rather than an
  error, so a blip never blanks the board.
- The page polls `/api/board` every 45s, pauses while the tab is hidden, and stops
  entirely once every game is final. It prefers the server, falls back to calling
  ESPN directly (works from a `file://` copy), and falls back again to the schedule
  embedded in the page.
- Anyone on the same network can open the machine's LAN address on that port.

## Where it lives
- **Site:** <https://owenliliu.github.io/wideout-board/> — the league's link.
- **Repo:** <https://github.com/owenliliu/wideout-board> (public; GitHub Pages on a
  free account requires it). Pushing to `main` redeploys in about a minute.
- `index.html` is a **complete HTML document** (doctype, `lang`, viewport, Open Graph
  tags). Do not strip that wrapper: without it Pages serves the page in quirks mode
  and phones lay it out at ~980px. Note this differs from what the Claude Artifact
  wants — the Artifact supplies its own wrapper — so publishing this same file as an
  Artifact would nest one. The website is now the canonical copy.

## Deploying it as a real website
**No server is required to host this.** ESPN's API sends
`access-control-allow-origin: *`, so the page can call it straight from any viewer's
browser. `server.py` is a convenience (one shared fetch, a cache, works offline), not
a dependency — dropping `index.html` on any static host gives a live, self-refreshing
site. Verified against a plain static server: with no `/api/board` present the page
falls back to ESPN directly and polls normally.

To keep that cheap, the page only pulls box scores for the games that actually contain
one of our receivers, and only once a game has left the `pre` state — before kickoff a
refresh is a single scoreboard request.

Hosts that need no build step and no Node: GitHub Pages (`gh` + a repo), Cloudflare
Pages, or Netlify (drag-and-drop). Note a deployed board is reachable by anyone with
the URL, and the page lists real league members' names.

## Known limitation — the shared Artifact cannot fetch
A published Artifact runs under a CSP that blocks non-Anthropic hosts, so inside the
Artifact the live fetch fails by design. The page detects it, removes the Refresh
button, and says so. Updating the league's Artifact copy means re-running the fetch
locally and republishing to the same URL. A real static deployment does not have this
limitation — that is the reason to prefer one.

## Workflow
1. Keep this file current when the roster, week, or rules change.
2. `index.html` is the whole app — keep it a single file.
3. Sanity-check ESPN responses with `curl` before wiring new fetch logic; the API is
   unofficial and undocumented. Note `site.api.espn.com` returns 403 from here —
   use **`site.web.api.espn.com`**, which works and sends `access-control-allow-origin: *`.
4. Verify rendering by screenshotting headless Chrome. It clamps the window to a
   500px minimum width, so a 390px screenshot is clipped, not overflowing — compare
   `document.documentElement.scrollWidth` against `window.innerWidth` to tell.
