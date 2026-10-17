import unittest
from types import SimpleNamespace

from backend.core.conversation import (
    MAX_HISTORY_MESSAGES,
    MAX_MESSAGE_CHARS,
    build_retrieval_query,
    format_history,
    normalize_history,
)


class NormalizeHistoryTests(unittest.TestCase):

    def test_maps_bot_to_assistant_and_accepts_text_or_content(self):
        out = normalize_history(
            [
                {"role": "user", "text": "tell me about BCA"},
                {"role": "bot", "content": "BCA is a 3 year course"},
            ],
            "what about fees",
        )
        self.assertEqual(
            out,
            [
                {"role": "user", "content": "tell me about BCA"},
                {"role": "assistant", "content": "BCA is a 3 year course"},
            ],
        )

    def test_drops_trailing_copy_of_current_question(self):
        # The frontend appends the new question to history before sending.
        out = normalize_history(
            [
                {"role": "user", "text": "first"},
                {"role": "bot", "text": "answer"},
                {"role": "user", "text": "second question"},
            ],
            "second question",
        )
        self.assertEqual([m["content"] for m in out], ["first", "answer"])

    def test_keeps_a_user_message_that_only_looks_similar(self):
        out = normalize_history([{"role": "user", "text": "BCA fees"}], "MCA fees")
        self.assertEqual(len(out), 1)

    def test_skips_empty_messages(self):
        out = normalize_history([{"role": "user", "text": "  "}, {"role": "bot"}], "q")
        self.assertEqual(out, [])

    def test_limits_count_and_length(self):
        raw = [{"role": "user", "text": "x" * 5000} for _ in range(20)]
        out = normalize_history(raw, "something else")
        self.assertEqual(len(out), MAX_HISTORY_MESSAGES)
        self.assertTrue(all(len(m["content"]) <= MAX_MESSAGE_CHARS for m in out))

    def test_accepts_objects_like_pydantic_models(self):
        item = SimpleNamespace(role="user", text="hello there", content=None)
        out = normalize_history([item], "next")
        self.assertEqual(out, [{"role": "user", "content": "hello there"}])

    def test_none_history(self):
        self.assertEqual(normalize_history(None, "q"), [])


class RetrievalQueryTests(unittest.TestCase):

    HISTORY = [
        {"role": "user", "content": "tell me about the BCA course"},
        {"role": "assistant", "content": "It is a three year program."},
    ]

    def test_short_follow_up_borrows_previous_user_question(self):
        self.assertEqual(
            build_retrieval_query("and the fees?", self.HISTORY),
            "tell me about the BCA course and the fees?",
        )

    def test_long_question_is_left_alone(self):
        q = "what is the last date to submit the examination form for third semester"
        self.assertEqual(build_retrieval_query(q, self.HISTORY), q)

    def test_no_history_is_left_alone(self):
        self.assertEqual(build_retrieval_query("and fees?", []), "and fees?")

    def test_only_assistant_messages_in_history(self):
        h = [{"role": "assistant", "content": "Hello!"}]
        self.assertEqual(build_retrieval_query("fees?", h), "fees?")


class FormatHistoryTests(unittest.TestCase):

    def test_empty(self):
        self.assertEqual(format_history([]), "")

    def test_marks_history_as_not_a_source_of_facts(self):
        block = format_history([{"role": "user", "content": "hi"}])
        self.assertIn("User: hi", block)
        self.assertIn("NOT a source of facts", block)


if __name__ == "__main__":
    unittest.main()
