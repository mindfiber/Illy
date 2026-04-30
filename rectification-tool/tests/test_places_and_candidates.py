from __future__ import annotations

import unittest
from datetime import date, time

from rectification_engine.candidates import generate_minute_candidates
from rectification_engine.models import BirthData
from rectification_engine.places import resolve_place


class PlacesAndCandidatesTests(unittest.TestCase):
    def test_resolve_incheon_korean_name(self):
        place = resolve_place("인천")

        self.assertEqual(place.name, "Incheon")
        self.assertEqual(place.latitude, 37.4563)
        self.assertEqual(place.longitude, 126.7052)
        self.assertEqual(place.timezone, "Asia/Seoul")

    def test_birth_data_from_strings_resolves_place(self):
        birth = BirthData.from_strings("1981.10.13", "03:45", "인천")

        self.assertEqual(birth.birth_date, date(1981, 10, 13))
        self.assertEqual(birth.birth_time, time(3, 45))
        self.assertEqual(birth.place.name, "Incheon")
        self.assertEqual(birth.place.timezone, "Asia/Seoul")

    def test_generate_minute_candidates_inclusive(self):
        candidates = generate_minute_candidates("03:43", "03:45")

        self.assertEqual([c.candidate_id for c in candidates], ["BT_03:43", "BT_03:44", "BT_03:45"])
        self.assertEqual([c.birth_time for c in candidates], [time(3, 43), time(3, 44), time(3, 45)])


if __name__ == "__main__":
    unittest.main()
