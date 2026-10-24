"""Tests for the hand-written Traditional->Simplified converter."""
import unittest

from accesshk.l10n import to_simplified


class TestL10n(unittest.TestCase):
    def test_known_station_names(self):
        cases = {
            "金鐘": "金钟", "灣仔": "湾仔", "鰂魚涌": "鲗鱼涌",
            "將軍澳": "将军澳", "鑽石山": "钻石山", "觀塘": "观塘",
            "奧運": "奥运", "大圍": "大围", "堅尼地城": "坚尼地城",
            "香港大學": "香港大学", "落馬洲": "落马洲", "調景嶺": "调景岭",
        }
        for trad, simp in cases.items():
            self.assertEqual(to_simplified(trad), simp)

    def test_identical_text_unchanged(self):
        self.assertEqual(to_simplified("北角"), "北角")
        self.assertEqual(to_simplified("Kowloon Tong"), "Kowloon Tong")
        self.assertEqual(to_simplified(""), "")

    def test_single_character_map_is_char_by_char(self):
        # every key/value in the map must be single characters
        from accesshk.l10n import _T2S
        for k, v in _T2S.items():
            self.assertEqual(len(k), 1, f"multi-char key: {k}")
            self.assertEqual(len(v), 1, f"multi-char value: {v}")


if __name__ == "__main__":
    unittest.main()
