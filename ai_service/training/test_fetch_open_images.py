import unittest
from fetch_open_images import author_key, is_cc_by, select_images


def meta(i, lic="https://creativecommons.org/licenses/by/2.0/", url="http://x/1.jpg"):
    return {"ImageID": i, "License": lic, "OriginalURL": url}


def lab(i, mid, c="1"):
    return {"ImageID": i, "LabelName": mid, "Confidence": c}


class Tests(unittest.TestCase):
    def test_only_plain_cc_by(self):
        for ok in ["https://creativecommons.org/licenses/by/2.0/", "http://creativecommons.org/licenses/by/4.0"]:
            self.assertTrue(is_cc_by(ok), ok)
        for bad in ["https://creativecommons.org/licenses/by-nc/2.0/", "https://creativecommons.org/licenses/by-sa/2.0/",
                    "https://creativecommons.org/licenses/by-nd/2.0/", "", None, "https://creativecommons.org/publicdomain/mark/1.0/"]:
            self.assertFalse(is_cc_by(bad), bad)

    def test_selection_filters_license_plants_and_confidence(self):
        labels = [lab("a", "P"), lab("b", "P"), lab("b", "PLANT"), lab("c", "P"), lab("d", "P", c="0"), lab("e", "P")]
        metas = [meta("a"), meta("b"), meta("c", lic="https://creativecommons.org/licenses/by-nc/2.0/"), meta("d"), meta("e", url="")]
        got = select_images(["P"], {"PLANT"}, labels, metas, per_label=10, seed=0)
        self.assertEqual([r["ImageID"] for _, r in got], ["a"])  # b has plant, c NC, d neg label, e no url

    def test_per_label_cap_and_no_duplicate_images(self):
        labels = [lab(f"i{n}", m) for n in range(10) for m in ("P", "Q")]
        metas = [meta(f"i{n}") for n in range(10)]
        got = select_images(["P", "Q"], set(), labels, metas, per_label=3, seed=1)
        ids = [r["ImageID"] for _, r in got]
        self.assertEqual(len(ids), 6); self.assertEqual(len(set(ids)), 6)

    def test_author_key_stable_and_prefers_profile(self):
        self.assertEqual(author_key("u", "n", "i"), author_key("u", "other", "j"))
        self.assertNotEqual(author_key("", "", "i"), author_key("", "", "j"))


if __name__ == "__main__":
    unittest.main()
