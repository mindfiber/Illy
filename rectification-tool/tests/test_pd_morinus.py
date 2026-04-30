from __future__ import annotations

import unittest
from pathlib import Path

from rectification_engine.models import BirthData
from rectification_engine.morinus_parser import parse_morinus_pd_file
from rectification_engine.natal import calculate_natal_points, expand_antiscia
from rectification_engine.pd_morinus import (
    morinus_create_arc,
    zodiacal_promissor_aspect_to_mc,
    zodiacal_promissor_to_significator_aspect,
)

try:
    import swisseph  # noqa: F401
except ImportError:
    HAS_SWISSEPH = False
else:
    HAS_SWISSEPH = True


def morinus_0345_birth() -> BirthData:
    return BirthData.from_strings("1981.10.13", "03:45:53", "morinus_0345")


RANGE_FIXTURE = Path(__file__).parent / "fixtures" / "morinus_0325_0405"


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

    @unittest.skipUnless(HAS_SWISSEPH, "swisseph is not installed for this Python interpreter")
    def test_0325_0405_zodiacal_sun_antiscia_to_mc_tracks_morinus(self):
        max_diff = 0.0
        paths = sorted(RANGE_FIXTURE.glob("*.txt"))
        self.assertEqual(len(paths), 41)
        for path in paths:
            hhmm = f"{path.stem[:2]}:{path.stem[2:]}:25"
            birth = BirthData.from_strings("1981.10.13", hhmm, "morinus_0345")
            points = expand_antiscia(calculate_natal_points(birth))
            hits = parse_morinus_pd_file(path)

            expected_ant = next(
                hit
                for hit in hits
                if hit.mode == "Z"
                and hit.promissor == "Antiscion Sun"
                and hit.aspect == "Quadrat"
                and hit.significator == "MC"
            )
            expected_contra = next(
                hit
                for hit in hits
                if hit.mode == "Z"
                and hit.promissor == "Contraantiscion Sun"
                and hit.aspect == "Quadrat"
                and hit.significator == "MC"
            )

            calc_ant = zodiacal_promissor_aspect_to_mc(
                birth,
                promissor_name="Antiscion Sun",
                aspect_name="Quadrat",
                aspect_sign=1,
                points=points,
            )
            calc_contra = zodiacal_promissor_aspect_to_mc(
                birth,
                promissor_name="Contraantiscion Sun",
                aspect_name="Quadrat",
                aspect_sign=-1,
                points=points,
            )

            self.assertEqual(calc_ant.direction, expected_ant.direction)
            self.assertEqual(calc_contra.direction, expected_contra.direction)
            max_diff = max(
                max_diff,
                abs(calc_ant.arc - float(expected_ant.arc)),
                abs(calc_contra.arc - float(expected_contra.arc)),
            )

        self.assertLess(max_diff, 0.00001)

    @unittest.skipUnless(HAS_SWISSEPH, "swisseph is not installed for this Python interpreter")
    def test_0325_0405_zodiacal_mc_antiscia_to_square_sun_tracks_morinus(self):
        max_diff = 0.0
        paths = sorted(RANGE_FIXTURE.glob("*.txt"))
        self.assertEqual(len(paths), 41)
        for path in paths:
            hhmm = f"{path.stem[:2]}:{path.stem[2:]}:25"
            birth = BirthData.from_strings("1981.10.13", hhmm, "morinus_0345")
            points = expand_antiscia(calculate_natal_points(birth))
            hits = parse_morinus_pd_file(path)

            expected_ant = next(
                hit
                for hit in hits
                if hit.mode == "Z"
                and hit.promissor == "Antiscion MC"
                and hit.aspect == "Quadrat"
                and hit.significator == "Sun"
            )
            expected_contra = next(
                hit
                for hit in hits
                if hit.mode == "Z"
                and hit.promissor == "Contraantiscion MC"
                and hit.aspect == "Quadrat"
                and hit.significator == "Sun"
            )

            calc_ant = zodiacal_promissor_to_significator_aspect(
                birth,
                promissor_name="Antiscion MC",
                significator_name="Sun",
                aspect_name="Quadrat",
                aspect_sign=-1,
                points=points,
            )
            calc_contra = zodiacal_promissor_to_significator_aspect(
                birth,
                promissor_name="Contraantiscion MC",
                significator_name="Sun",
                aspect_name="Quadrat",
                aspect_sign=-1,
                points=points,
            )

            self.assertEqual(calc_ant.direction, expected_ant.direction)
            self.assertEqual(calc_contra.direction, expected_contra.direction)
            max_diff = max(
                max_diff,
                abs(calc_ant.arc - float(expected_ant.arc)),
                abs(calc_contra.arc - float(expected_contra.arc)),
            )

        self.assertLess(max_diff, 0.00001)

    @unittest.skipUnless(HAS_SWISSEPH, "swisseph is not installed for this Python interpreter")
    def test_0325_0405_zodiacal_sun_jupiter_conjunctions_track_morinus(self):
        max_diff = 0.0
        paths = sorted(RANGE_FIXTURE.glob("*.txt"))
        self.assertEqual(len(paths), 41)
        pairs = [("Sun", "Jupiter"), ("Jupiter", "Sun")]

        for path in paths:
            hhmm = f"{path.stem[:2]}:{path.stem[2:]}:25"
            birth = BirthData.from_strings("1981.10.13", hhmm, "morinus_0345")
            points = expand_antiscia(calculate_natal_points(birth))
            hits = parse_morinus_pd_file(path)

            for promissor, significator in pairs:
                expected = next(
                    hit
                    for hit in hits
                    if hit.mode == "Z"
                    and hit.promissor == promissor
                    and hit.aspect == "Conjunctio"
                    and hit.significator == significator
                )
                calculated = zodiacal_promissor_to_significator_aspect(
                    birth,
                    promissor_name=promissor,
                    significator_name=significator,
                    aspect_name="Conjunctio",
                    aspect_sign=1,
                    points=points,
                )

                self.assertEqual(calculated.direction, expected.direction)
                max_diff = max(max_diff, abs(calculated.arc - float(expected.arc)))

        self.assertLess(max_diff, 0.00002)


if __name__ == "__main__":
    unittest.main()
