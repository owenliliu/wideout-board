# The Wideout Board

A live draft-order tracker for our fantasy league. Everyone called one NFL wide
receiver before the final week of the 2026 preseason; most receiving yards takes the
first pick, fewest takes last.

**[Open the board](index.html)** — it updates itself while the games are on.

## How it works

`index.html` is the entire site: one file, no build step, no dependencies. It reads
the week's receiving lines from ESPN's public API and re-checks every 45 seconds,
pausing while the tab is hidden and stopping once every game is final.

Nothing is ranked before it's real — a manager's slot shows `—` until an actual
figure decides it, and a receiver who didn't play is shown as absent rather than as
a zero.

## Running it locally

Just open `index.html`, or run the small server for a shared, cached copy:

    python3 server.py          # http://localhost:8765

The server (Python standard library only) does one ESPN fetch on behalf of every
open tab, caches it briefly, and keeps serving the last good figures if ESPN blips.
It reads the roster straight out of `index.html`, so that file is the only place the
league's picks are written down.
