"""Offline checks of the curation scripts: no network, no Mapillary token.

    python -m unittest scripts/curation/test_curation.py     (needs shapely, mapbox-vector-tile, pillow)

The first group pins the zones pool.py plans in, Ukraine's above all: the west
and the centre are in, the front line, the occupied south and east and Crimea
are out. The second pins the reasons harvest.py counts when a tile gives no frame.
"""
import os, random, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("MAPILLARY_TOKEN", "offline")
os.environ.pop("MAPLY_AVOID", None)
sys.argv = [sys.argv[0], tempfile.mkdtemp()]  # harvest.py reads its output folder on import

import harvest, pool
from regions import REGIONS

IN = {
    "Kyiv": (50.45, 30.52), "Lviv": (49.84, 24.03), "Odesa": (46.48, 30.73),
    "Vinnytsia": (49.23, 28.47), "Uzhhorod": (48.62, 22.29), "Chernivtsi": (48.29, 25.94),
    "Ivano-Frankivsk": (48.92, 24.71), "Zhytomyr": (50.25, 28.66), "Rivne": (50.62, 26.25),
    "Cherkasy": (49.44, 32.06),
    # The city itself is in (owner decision, 2026-11-23), not its region.
    "Kharkiv": (49.99, 36.23),
}
OUT = {
    "Simferopol": (44.95, 34.1), "Sevastopol": (44.6, 33.53), "Donetsk": (48.0, 37.8),
    "Luhansk": (48.57, 39.3), "Mariupol": (47.1, 37.55), "Melitopol": (46.85, 35.37),
    "Kherson": (46.64, 32.6), "Zaporizhzhia": (47.84, 35.14), "Kupiansk": (49.71, 37.62),
    "Chuhuiv": (49.84, 36.69), "Sumy": (50.9, 34.8),
}


class Zones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.countries = pool.load_countries()

    def test_west_and_centre_are_planned_in(self):
        for name, (lat, lon) in IN.items():
            with self.subTest(name):
                self.assertEqual(pool.country_of(self.countries, lat, lon), "UA")
                self.assertTrue(pool.allowed("UA", lat, lon))

    def test_front_line_and_occupied_land_stay_out(self):
        for name, (lat, lon) in OUT.items():
            with self.subTest(name):
                self.assertFalse(pool.allowed("UA", lat, lon))

    def test_a_random_point_is_in_ukraine_and_in_a_zone_kept(self):
        random.seed(1)
        for _ in range(200):
            lat, lon = pool.random_in(self.countries["UA"], "UA")
            self.assertEqual(pool.country_of(self.countries, lat, lon), "UA")
            self.assertTrue(pool.allowed("UA", lat, lon))

    def test_the_big_cities_of_the_built_in_list(self):
        # harvest.py's own list does not filter by zone; pool.py does. The
        # list holds the Ukrainian cities, and Poltava is the one left out.
        ua = {n: (la, lo) for n, la, lo, _ in REGIONS if pool.country_of(self.countries, la, lo) == "UA"}
        self.assertEqual({n for n, p in ua.items() if not pool.allowed("UA", *p)}, {"Полтава"})
        self.assertEqual(len(ua), 8)


def tile(*frames):
    """What mapbox_vector_tile.decode returns for a z14 tile of these frames."""
    return {"image": {"features": [
        {"geometry": {"type": "Point", "coordinates": [2048 + i, 2048]}, "properties": p}
        for i, p in enumerate(frames)]}}


def frame(i, pano=True, quality=0.9, ts=1589816581000):
    return {"id": i, "is_pano": pano, "quality_score": quality, "captured_at": ts}


class Reasons(unittest.TestCase):
    def run_region(self, t, kind="town"):
        harvest.REJECTS.clear()
        region = {"name": "x", "lat": 49.4, "lon": 31.3, "km": 0.3, "inner": 0, "kind": kind, "country": "UA"}
        with mock.patch.object(harvest, "get", return_value=b""), \
             mock.patch.object(harvest.mapbox_vector_tile, "decode", return_value=t):
            self.assertIsNone(harvest.harvest(region))
        return dict(harvest.REJECTS["UA"])

    def test_a_tile_of_flat_frames(self):
        r = self.run_region(tile(frame(1, pano=False), frame(2, pano=False)))
        self.assertEqual(r, {"frames, none a panorama": 12})

    def test_a_panorama_under_the_quality_bar(self):
        r = self.run_region(tile(frame(1, quality=0.5), frame(2, quality=None)))
        self.assertEqual(r, {"panoramas, none at quality 0.7": 12})

    def test_frames_before_2018(self):
        r = self.run_region(tile(frame(1, ts=1400000000000)))
        self.assertEqual(r, {"no frame since 2018 in the tile": 12})

    def test_a_town_whose_panoramas_are_beyond_its_nearest_frames(self):
        # 40 flat frames nearer the centre than the one panorama, as a dashcam town has.
        t = tile(*[frame(i, pano=False) for i in range(40)], frame(99))
        t["image"]["features"][-1]["geometry"]["coordinates"] = [4000, 4000]
        r = self.run_region(t)
        self.assertEqual(r, {"panoramas only beyond the 40 nearest frames": 12})


if __name__ == "__main__":
    unittest.main()
