from __future__ import annotations

import unittest

from rectification_engine.models import BirthData, Place
from rectification_engine.natal import calculate_natal_points, expand_antiscia
from rectification_engine.pd_morinus import (
    morinus_create_arc,
    zodiacal_promissor_aspect_to_mc,
)

try:
    import swisseph  # noqa: F401
except ImportError:
    HAS_SWISSEPH = False
else:
    HAS_SWISSEPH = True


def morinus_0345_birth() -> BirthData:
    return BirthData.from_strings("1981.10.13", "03:45:53", "morinus_0345")


class MorinusPDTests(unittest.TestCase):
    def test_morinus_create_arc_converse(self):
        arc = morinus_create_arc(-0.332874)

        self.assertEqual(arc.direction, "C")
        self.assertAlmostEqual(arc.arc, 0.332874, places=6)

    @unittest.skipUnless(HAS_SWISSEPH, "swisseph is not installed for this Python interpreter")
    def test_0345_zodiacal_quadrat_contraantiscion_sun_to_mc(self):
        birth = morinus_0345_birth()
        points = expand_antiscia(calculate_natal_points(birth))

        arc = zodiacal_promissor_aspect_to_mc(
            birth,
            promissor_name="Contraantiscion Sun",
            aspect_name="Quadrat",
            aspect_sign=-1,
            points=points,
        )

        self.assertEqual(arc.direction, "C")
        self.assertAlmostEqual(arc.arc, 0.332874, places=5)

    @unittest.skipUnless(HAS_SWISSEPH, "swisseph is not installed for this Python interpreter")
    def test_0345_zodiacal_quadrat_antiscion_sun_to_mc(self):
        birth = morinus_0345_birth()
        points = expand_antiscia(calculate_natal_points(birth))

        arc = zodiacal_promissor_aspect_to_mc(
            birth,
            promissor_name="Antiscion Sun",
            aspect_name="Quadrat",
            aspect_sign=1,
            points=points,
        )

        self.assertEqual(arc.direction, "C")
        self.assertAlmostEqual(arc.arc, 0.332874, places=5)


if __name__ == "__main__":
    unittest.main()
