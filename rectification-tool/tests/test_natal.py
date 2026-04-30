from __future__ import annotations

import unittest

from rectification_engine.models import BirthData
from rectification_engine.natal import (
    antiscia,
    calculate_natal_points,
    contra_antiscia,
    expand_antiscia,
    is_day_chart,
    julian_day_ut,
    norm360,
)

try:
    import swisseph  # noqa: F401
except ImportError:
    HAS_SWISSEPH = False
else:
    HAS_SWISSEPH = True


class NatalTests(unittest.TestCase):
    def test_norm360(self):
        self.assertEqual(norm360(360), 0.0)
        self.assertEqual(norm360(-1), 359.0)

    def test_antiscia_helpers(self):
        self.assertEqual(antiscia(10.0), 170.0)
        self.assertEqual(contra_antiscia(10.0), 350.0)
        self.assertEqual(antiscia(190.0), 350.0)
        self.assertEqual(contra_antiscia(190.0), 170.0)

    @unittest.skipUnless(HAS_SWISSEPH, "swisseph is not installed for this Python interpreter")
    def test_0345_julian_day_uses_incheon_timezone(self):
        birth = BirthData.from_strings("1981.10.13", "03:45", "인천")

        self.assertAlmostEqual(julian_day_ut(birth), 2444890.28125, places=6)

    @unittest.skipUnless(HAS_SWISSEPH, "swisseph is not installed for this Python interpreter")
    def test_calculate_0345_natal_points(self):
        birth = BirthData.from_strings("1981.10.13", "03:45", "인천")
        points = calculate_natal_points(birth)

        self.assertEqual(
            sorted(points),
            ["ASC", "Jupiter", "LoF", "MC", "Mars", "Mercury", "Moon", "Saturn", "Sun", "Venus"],
        )
        self.assertAlmostEqual(points["Sun"].longitude, 199.3487587, places=5)
        self.assertAlmostEqual(points["Moon"].longitude, 8.9505762, places=5)
        self.assertAlmostEqual(points["ASC"].longitude, 163.0174591, places=5)
        self.assertAlmostEqual(points["MC"].longitude, 70.7910467, places=5)
        self.assertFalse(is_day_chart(points["ASC"].longitude, points["Sun"].longitude))
        self.assertAlmostEqual(points["LoF"].longitude, 353.4156416, places=5)

    @unittest.skipUnless(HAS_SWISSEPH, "swisseph is not installed for this Python interpreter")
    def test_expand_antiscia_for_0345_points(self):
        birth = BirthData.from_strings("1981.10.13", "03:45", "인천")
        expanded = expand_antiscia(calculate_natal_points(birth))

        self.assertIn("Antiscion Sun", expanded)
        self.assertIn("Contraantiscion Sun", expanded)
        self.assertEqual(len(expanded), 30)
        self.assertAlmostEqual(expanded["Antiscion Sun"].longitude, 340.6512413, places=5)
        self.assertAlmostEqual(expanded["Contraantiscion Sun"].longitude, 160.6512413, places=5)


if __name__ == "__main__":
    unittest.main()
