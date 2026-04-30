from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from rectification_engine.morinus_parser import parse_morinus_pd_file, parse_morinus_pd_line


FIXTURE = Path(__file__).parent / "fixtures" / "morinus_0345" / "morinus_pd_raw.txt"


class MorinusParserTests(unittest.TestCase):
    def test_parse_first_morinus_pd_row(self):
        hit = parse_morinus_pd_line("Z Quadrat Contraantiscion Sun C --> MC 0.332874 1982.02.12")

        self.assertIsNotNone(hit)
        self.assertEqual(hit.mode, "Z")
        self.assertEqual(hit.aspect, "Quadrat")
        self.assertEqual(hit.promissor, "Contraantiscion Sun")
        self.assertEqual(hit.direction, "C")
        self.assertEqual(hit.significator, "MC")
        self.assertEqual(hit.arc, Decimal("0.332874"))
        self.assertEqual(hit.hit_date_raw, "1982.02.12")
        self.assertEqual(hit.hit_date, date(1982, 2, 12))

    def test_parse_implicit_conjunction_row(self):
        hit = parse_morinus_pd_line("M Jupiter D --> Sun 1.186010 1982.12.25")

        self.assertIsNotNone(hit)
        self.assertEqual(hit.mode, "M")
        self.assertEqual(hit.aspect, "Conjunctio")
        self.assertEqual(hit.promissor, "Jupiter")
        self.assertEqual(hit.direction, "D")
        self.assertEqual(hit.significator, "Sun")

    def test_parse_aspect_on_significator_side(self):
        hit = parse_morinus_pd_line("Z Antiscion MC C --> Quadrat Sun 0.348729 1982.02.18")

        self.assertIsNotNone(hit)
        self.assertEqual(hit.aspect, "Quadrat")
        self.assertEqual(hit.promissor, "Antiscion MC")
        self.assertEqual(hit.significator, "Sun")

    def test_parse_0345_fixture_count_and_edges(self):
        hits = parse_morinus_pd_file(FIXTURE)

        self.assertEqual(len(hits), 2501)
        self.assertEqual(hits[0].raw_line, "Z Quadrat Contraantiscion Sun C --> MC 0.332874 1982.02.12")
        self.assertEqual(hits[596].hit_date_raw, "2011.01.00")
        self.assertIsNone(hits[596].hit_date)
        self.assertGreaterEqual(hits[-1].arc, hits[0].arc)


if __name__ == "__main__":
    unittest.main()
