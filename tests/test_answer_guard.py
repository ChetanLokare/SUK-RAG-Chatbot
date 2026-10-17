import sys
import types
import unittest

# answer_guard imports the real LLM service (OpenAI/Gemini SDKs). Replace it
# with a controllable fake so these tests need no network and no API keys.
_fake_llm = types.ModuleType("backend.services.llm_service")
_fake_llm.calls = []
_fake_llm.reply = None   # str, None, or an Exception instance


def _call_llm(prompt, question=None, temperature=0.3):
    _fake_llm.calls.append(prompt)
    if isinstance(_fake_llm.reply, Exception):
        raise _fake_llm.reply
    return _fake_llm.reply


_fake_llm.call_llm = _call_llm
sys.modules["backend.services.llm_service"] = _fake_llm

from backend.core import answer_guard  # noqa: E402
from backend.core.answer_guard import NOT_FOUND_MESSAGE, ensure_answer  # noqa: E402

CONTEXT = (
    "The last date for the examination form is 15 March. "
    "The library is open from 9 am to 5 pm."
)
GOOD = "The last date to submit the examination form is 15 March, per the notice."


class EnsureAnswerTests(unittest.TestCase):

    def setUp(self):
        _fake_llm.calls.clear()
        _fake_llm.reply = None

    def test_good_answer_is_returned_untouched_without_extra_llm_calls(self):
        out = ensure_answer("exam form last date", CONTEXT, GOOD)
        self.assertEqual(out, GOOD)
        self.assertEqual(_fake_llm.calls, [])

    def test_empty_answer_gets_one_grounded_retry(self):
        _fake_llm.reply = GOOD
        out = ensure_answer("exam form last date", CONTEXT, None)
        self.assertEqual(out, GOOD)
        self.assertEqual(len(_fake_llm.calls), 1)
        self.assertIn("ONLY", _fake_llm.calls[0])
        self.assertIn("Do NOT invent", _fake_llm.calls[0])

    def test_no_context_never_calls_the_llm_and_never_makes_things_up(self):
        # Regression: the old guard asked the LLM for a "general academic
        # explanation" here, which is how fees/dates got invented.
        _fake_llm.reply = "The fee is Rs 5000 and the HOD is Dr. Patil."
        out = ensure_answer("what is the BCA fee", "", None)
        self.assertEqual(out, NOT_FOUND_MESSAGE)
        self.assertEqual(_fake_llm.calls, [])

    def test_llm_failure_falls_back_to_context_sentences(self):
        _fake_llm.reply = None
        out = ensure_answer("examination form last date", CONTEXT, "")
        self.assertIn("15 March", out)
        self.assertNotIn("library", out)

    def test_llm_exception_does_not_crash(self):
        _fake_llm.reply = RuntimeError("quota exceeded")
        out = ensure_answer("examination form last date", CONTEXT, None)
        self.assertIn("15 March", out)

    def test_unrelated_context_is_not_passed_off_as_an_answer(self):
        _fake_llm.reply = None
        out = ensure_answer("hostel mess menu", "Convocation is held in December.", None)
        self.assertEqual(out, NOT_FOUND_MESSAGE)

    def test_honest_decline_is_kept_when_nothing_better_exists(self):
        decline = "I could not find the hostel fees in the provided documents."
        _fake_llm.reply = decline  # retry declines too
        out = ensure_answer("hostel mess menu", "Convocation is held in December.", decline)
        self.assertEqual(out, decline)

    def test_decline_with_useful_context_gets_rechecked(self):
        decline = "I could not find that in the documents."
        _fake_llm.reply = GOOD
        out = ensure_answer("examination form last date", CONTEXT, decline)
        self.assertEqual(out, GOOD)

    def test_abbreviation_is_expanded_in_whole_words_only(self):
        _fake_llm.reply = GOOD
        ensure_answer("cs admit with dept", CONTEXT, None)
        prompt = _fake_llm.calls[0]
        self.assertIn("computer science", prompt)
        self.assertIn("admit with", prompt)   # not corrupted
        self.assertNotIn("wiinformation", prompt)


class WeaknessTests(unittest.TestCase):

    def test_weak(self):
        for a in [None, "", "ok", "I don't know the answer to that question at all."]:
            self.assertTrue(answer_guard._is_weak(a), a)

    def test_not_weak(self):
        self.assertFalse(answer_guard._is_weak(GOOD))


if __name__ == "__main__":
    unittest.main()
