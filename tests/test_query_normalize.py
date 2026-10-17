import unittest

from backend.utils.query_normalize import expand_abbreviations


class ExpandAbbreviationsTests(unittest.TestCase):

    def test_whole_words_are_expanded_and_original_kept(self):
        self.assertEqual(
            expand_abbreviations("cs dept fees"),
            "cs computer science dept department fees",
        )

    def test_hod(self):
        self.assertEqual(
            expand_abbreviations("who is the HOD"),
            "who is the HOD head of department",
        )

    def test_does_not_corrupt_words_that_contain_an_abbreviation(self):
        # The old str.replace() turned these into garbage.
        for word in ["with", "admit", "physics", "deptford", "methodology", "its"]:
            self.assertEqual(expand_abbreviations(word), word)

    def test_lowercase_it_is_just_english(self):
        self.assertEqual(expand_abbreviations("is it open today"), "is it open today")

    def test_capital_IT_means_information_technology(self):
        self.assertEqual(
            expand_abbreviations("IT department contact"),
            "IT information technology department contact",
        )

    def test_marathi_and_hindi_text_untouched(self):
        text = "शिवाजी विद्यापीठ परीक्षा शुल्क"
        self.assertEqual(expand_abbreviations(text), text)

    def test_empty(self):
        self.assertEqual(expand_abbreviations(""), "")
        self.assertEqual(expand_abbreviations(None), "")

    def test_lowercasing_after_expansion_like_hybrid_search_does(self):
        self.assertEqual(
            expand_abbreviations("IT dept").lower(),
            "it information technology dept department",
        )


if __name__ == "__main__":
    unittest.main()
