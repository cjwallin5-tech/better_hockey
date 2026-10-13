"""Fetch a full past regular season of play-by-play and keep only the shot attempts.

Resumable: re-running skips games already saved. Usage: python train_xg_fetch.py 2025 [out.jsonl.gz]
"""
import gzip, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import config, ingest, shots

year = int(sys.argv[1])
out = Path(sys.argv[2] if len(sys.argv) > 2 else f"data/shots_{year}.jsonl.gz")
GAMES = 1312  # 32 teams x 82 games / 2

done = set()
if out.exists():
    with gzip.open(out, "rt") as f:
        done = {json.loads(line)["game_id"] for line in f}
todo = [int(f"{year}02{n:04d}") for n in range(1, GAMES + 1) if int(f"{year}02{n:04d}") not in done]
print(f"{len(done)} games saved, {len(todo)} to fetch", flush=True)


def grab(gid):
    try:
        pbp = ingest.get_json(f"{config.WEB_API}/gamecenter/{gid}/play-by-play")
    except Exception as e:  # missing game ids etc.
        return gid, None, str(e)
    time.sleep(0.25)
    if pbp.get("gameState") not in ("OFF", "FINAL"):
        return gid, None, "not final"
    return gid, shots.extract_shots(pbp), None


with gzip.open(out, "at") as f, ThreadPoolExecutor(max_workers=2) as pool:
    for i, (gid, rows, err) in enumerate(pool.map(grab, todo), 1):
        if rows is not None:
            f.write(json.dumps({"game_id": gid, "shots": rows}) + "\n")
        if i % 50 == 0:
            f.flush()
            print(f"  {i}/{len(todo)}", flush=True)
print("done")
