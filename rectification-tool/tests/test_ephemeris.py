from __future__ import annotations

import unittest

from rectification_engine.ephemeris import configure_swisseph, find_ephemeris_path

try:
    import swisseph  # noqa: F401
except ImportError:
    HAS_SWISSEPH = False
else:
    HAS_SWISSEPH = True


class EphemerisTests(unittest.TestCase):
    def test_local_ephemeris_path_exists(self):
        path = find_ephemeris_path()

        self.assertIsNotNone(path)
        self.assertTrue((path / "sepl_18.se1").exists())
        self.assertTrue((path / "semo_18.se1").exists())

    @unittest.skipUnless(HAS_SWISSEPH, "swisseph is not installed for this Python interpreter")
    def test_swisseph_smoke_calculation(self):
        swe = configure_swisseph()
        jd_ut = swe.julday(1981, 10, 12, 18.75)
        position, flags = swe.calc_ut(jd_ut, swe.SUN)

        self.assertEqual(len(position), 6)
        self.assertGreaterEqual(position[0], 0.0)
        self.assertLess(position[0], 360.0)
        self.assertIsInstance(flags, int)


if __name__ == "__main__":
    unittest.main()
