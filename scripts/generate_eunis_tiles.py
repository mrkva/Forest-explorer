#!/usr/bin/env python3
"""Generate EUNIS raster data tiles from EEA Ecosystem Type Map.

Exports small PNG images from the ArcGIS MapServer export endpoint for each z12
tile covering Slovakia. The PNG pixel values encode EUNIS habitat codes, which
the client reads via canvas getImageData.

Usage:
    python3 scripts/generate_eunis_tiles.py [--workers 4] [--resume]

Requires: Python 3.6+ (stdlib only, no dependencies)
"""

import argparse
import concurrent.futures
import math
import os
import sys
import threading
import time
import urllib.error
import urllib.request

# Slovakia bounding box
SK_SOUTH, SK_NORTH = 47.73, 49.61
SK_WEST, SK_EAST = 16.83, 22.57

ZOOM = 12
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'eunis', str(ZOOM))

# EEA Ecosystem Type Map v3.1 (Terrestrial) — EUNIS Level 2
EXPORT_URL = 'https://bio.discomap.eea.europa.eu/arcgis/rest/services/Ecosystem/EcosystemTypeMap_v3_1_Terrestrial/MapServer/export'

# Export as 8-bit PNG at reasonable resolution
# Each z12 tile is ~6-10 km wide, 100m resolution → ~60-100 pixels
TILE_SIZE = 64  # pixels per tile edge

MAX_RETRIES = 4
RETRY_DELAY = 5


def latlng_to_tile(lat, lng, z):
    n = 2 ** z
    x = int((lng + 180) / 360 * n)
    lat_rad = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
    return x, y


def tile_bounds(x, y, z):
    """Return (west, south, east, north) for a tile."""
    n = 2 ** z
    west = x / n * 360 - 180
    east = (x + 1) / n * 360 - 180
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def get_tiles():
    x_min, y_min = latlng_to_tile(SK_NORTH, SK_WEST, ZOOM)
    x_max, y_max = latlng_to_tile(SK_SOUTH, SK_EAST, ZOOM)
    tiles = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append((x, y))
    return tiles


def fetch_tile_image(x, y):
    """Export a small PNG from the ArcGIS MapServer for a single tile."""
    west, south, east, north = tile_bounds(x, y, ZOOM)
    # Use Web Mercator (3857) for the export since the source raster is in 3857
    # But provide bbox in 4326 and let the server reproject
    params = (
        f'?bbox={west},{south},{east},{north}'
        f'&bboxSR=4326'
        f'&imageSR=4326'
        f'&size={TILE_SIZE},{TILE_SIZE}'
        f'&format=png8'
        f'&layers=show:0'
        f'&transparent=false'
        f'&f=image'
    )
    url = EXPORT_URL + params

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'HabitatExplorer-TileGen/1.0',
                'Referer': 'https://mrkva.github.io/slovak-habitat-explorer/',
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                content_type = resp.headers.get('Content-Type', '')
                if 'image' not in content_type:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    return None
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                return None
    return None


def main():
    parser = argparse.ArgumentParser(description='Generate EUNIS raster tiles')
    parser.add_argument('--workers', type=int, default=4,
                        help='Number of parallel workers (default: 4)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show tile count without fetching')
    args = parser.parse_args()

    tiles = get_tiles()
    print(f"Slovakia coverage: {len(tiles)} tiles at z{ZOOM}")
    print(f"Output: {OUTPUT_DIR}")

    if args.dry_run:
        print(f"  eunis: {len(tiles)} tiles to generate")
        return

    # Filter to tiles that need work (resume)
    todo = []
    skipped = 0
    for (x, y) in tiles:
        tile_path = os.path.join(OUTPUT_DIR, str(x), f'{y}.png')
        if os.path.exists(tile_path):
            skipped += 1
        else:
            todo.append((x, y))

    print(f"\n=== eunis === ({len(tiles)} tiles, {skipped} cached, {len(todo)} to fetch)")

    if not todo:
        print("  Nothing to do!")
        return

    saved = 0
    errors = 0
    lock = threading.Lock()
    rate_lock = threading.Lock()
    last_request_time = [0.0]
    min_interval = 0.25  # 4 req/sec
    start_time = time.time()

    def process_tile(xy):
        nonlocal saved, errors
        x, y = xy

        with rate_lock:
            now = time.time()
            wait = min_interval - (now - last_request_time[0])
            if wait > 0:
                time.sleep(wait)
            last_request_time[0] = time.time()

        data = fetch_tile_image(x, y)

        with lock:
            if data:
                tile_dir = os.path.join(OUTPUT_DIR, str(x))
                os.makedirs(tile_dir, exist_ok=True)
                tile_path = os.path.join(tile_dir, f'{y}.png')
                with open(tile_path, 'wb') as f:
                    f.write(data)
                saved += 1
            else:
                errors += 1

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_tile, xy): xy for xy in todo}
        for future in concurrent.futures.as_completed(futures):
            done += 1
            if done % 25 == 0 or done == len(todo):
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(todo) - done) / rate if rate > 0 else 0
                print(f"  [{done}/{len(todo)}] saved={saved} err={errors}"
                      f"  ({rate:.1f}/s, ETA {int(eta)}s)")

    print(f"  Done: {saved} saved, {errors} errors, {skipped} skipped")


if __name__ == '__main__':
    main()
