"""Collect candidate places of the day from Panoramax.

Mapillary serves no image for any frame in Ukraine (see issue #45), so
Ukraine comes from Panoramax. This is harvest.py for Panoramax: the same
batch layout, so screen.py, choose.py, maply-places and faces.py read it as
they read a Mapillary batch.

For every region of the plan it asks Panoramax's search for the pictures
within the region's radius and keeps one: a 360° equirectangular panorama
captured in 2018 or later, with a known direction (view:azimuth, which
becomes the game's compass heading), in a part of a country pool.allowed()
lets in. Among those it takes the largest original, then the newest.

    python -I harvest_px.py <out> <plan.json>

plan.json is a list of {"region": "Kyiv, UA", "lat": 50.41, "lon": 30.52,
"km": 3, "kind": "city"}; kind is the scene (city, town or nature). An
"id" names the picture a reviewer picked from the region's sequence; it
still has to pass the same checks.

Output: <out>/candidates.json and <out>/full/NNN.jpg, the panorama scaled to
4096 px wide, the width maply-places -sharpen gives Mapillary panoramas.
A region with nothing usable says why.
"""
import io, json, math, os, sys, time, urllib.request
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("MAPILLARY_TOKEN", "")  # pool.py reads it at import; nothing here calls Mapillary
import pool

API = "https://api.panoramax.xyz/api/search"
UA = pool.UA
MIN_DATE = "2018"
WIDTH = 4096


def get(url, timeout=120):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def usable(f, countries):
    """The reason a picture is passed over, or "" when it can be a candidate."""
    p = f["properties"]
    if (p.get("pers:interior_orientation") or {}).get("field_of_view") != 360:
        return "not a 360° panorama"
    if p.get("view:azimuth") is None:
        return "no direction"
    if (p.get("datetime") or "") < MIN_DATE:
        return "before 2018"
    lon, lat = f["geometry"]["coordinates"]
    iso = pool.country_of(countries, lat, lon)
    if not iso or not pool.allowed(iso, lat, lon):
        return "in a part left out"
    if "hd" not in f.get("assets", {}):
        return "no original"
    return ""


def main():
    out, plan_path = sys.argv[1], sys.argv[2]
    plan = json.load(open(plan_path))
    countries = pool.load_countries()
    os.makedirs(f"{out}/full", exist_ok=True)
    cands = []
    for r in plan:
        d = r.get("km", 3) / 111
        dl = d / math.cos(math.radians(r["lat"]))
        bbox = f"{r['lon'] - dl},{r['lat'] - d},{r['lon'] + dl},{r['lat'] + d}"
        feats = json.loads(get(f"{API}?bbox={bbox}&limit=500")).get("features", [])
        why = {}
        ok = []
        for f in feats:
            reason = usable(f, countries)
            if reason:
                why[reason] = why.get(reason, 0) + 1
            else:
                ok.append(f)
        if not ok:
            print(f"{r['region']}: nothing of {len(feats)} pictures: {why}", file=sys.stderr)
            continue
        ok.sort(key=lambda f: (f["properties"].get("original_file:size") or 0, f["properties"]["datetime"]), reverse=True)
        if r.get("id"):
            ok = [f for f in ok if f["id"] == r["id"]]
            if not ok:
                print(f"{r['region']}: picture {r['id']} is not usable or not within {r.get('km', 3)} km", file=sys.stderr)
                continue
        f = ok[0]
        p = f["properties"]
        n = len(cands) + 1
        im = Image.open(io.BytesIO(get(f["assets"]["hd"]["href"]))).convert("RGB")
        if im.width > WIDTH:
            im = im.resize((WIDTH, WIDTH // 2), Image.LANCZOS)
        im.save(f"{out}/full/{n:03d}.jpg", quality=92)
        lon, lat = f["geometry"]["coordinates"]
        producer = p.get("geovisio:producer") or next(
            (x.get("name") for x in f.get("providers", []) if "producer" in x.get("roles", [])), "")
        cands.append({
            "n": n, "region": r["region"], "kind": r.get("kind", "city"),
            "country": pool.country_of(countries, lat, lon),
            "source": "panoramax", "source_id": f["id"],
            "lat": lat, "lon": lon, "is_pano": True,
            "captured_at": int(time.mktime(time.strptime(p["datetime"][:19], "%Y-%m-%dT%H:%M:%S")) * 1000),
            "heading": float(p["view:azimuth"]),
            "author": producer, "license": p.get("license") or "CC-BY-SA-4.0",
        })
        print(f"{n:03d} {r['region']}: {len(ok)} of {len(feats)} usable, took {f['id']} ({p['datetime'][:10]}, {im.width} px)", file=sys.stderr)
    json.dump(cands, open(f"{out}/candidates.json", "w"), ensure_ascii=False, indent=1)
    print(f"candidates: {len(cands)} of {len(plan)} regions", file=sys.stderr)


if __name__ == "__main__":
    main()
