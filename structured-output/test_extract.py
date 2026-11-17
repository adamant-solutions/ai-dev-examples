import json
import unittest

from pydantic import BaseModel, Field, ValidationError

import extract
from fake_model import FakeModel

GOOD = '{"category": "bug", "priority": 2, "summary": "Login fails", "needs_human": true}'


class LaxTicket(BaseModel):
    """Same fields, default (lax) settings: shows what strict mode changes."""

    category: str
    priority: int = Field(ge=1, le=5)
    needs_human: bool


class ValidationTests(unittest.TestCase):
    def test_valid_json_passes(self):
        t = extract.Ticket.model_validate_json(GOOD)
        self.assertEqual((t.category, t.priority, t.needs_human), ("bug", 2, True))

    def test_lax_mode_quietly_coerces_strings(self):
        t = LaxTicket.model_validate_json('{"category": "bug", "priority": "3", "needs_human": "yes"}')
        self.assertEqual((t.priority, t.needs_human), (3, True))  # "3" -> 3 and "yes" -> True

    def test_strict_mode_rejects_the_same_input(self):
        with self.assertRaises(ValidationError) as cm:
            extract.Ticket.model_validate_json(
                '{"category": "bug", "priority": "3", "summary": "x", "needs_human": "yes"}')
        types = {e["type"] for e in cm.exception.errors()}
        self.assertEqual(types, {"int_type", "bool_type"})

    def test_extra_field_is_an_error(self):
        with self.assertRaises(ValidationError) as cm:
            extract.Ticket.model_validate_json(GOOD[:-1] + ', "confidence": 0.9}')
        self.assertEqual(cm.exception.errors()[0]["type"], "extra_forbidden")

    def test_value_outside_enum_and_range(self):
        with self.assertRaises(ValidationError) as cm:
            extract.Ticket.model_validate_json(
                '{"category": "urgent", "priority": 9, "summary": "x", "needs_human": false}')
        self.assertEqual({e["type"] for e in cm.exception.errors()}, {"literal_error", "less_than_equal"})

    def test_truncated_json_is_json_invalid(self):
        with self.assertRaises(ValidationError) as cm:
            extract.Ticket.model_validate_json(GOOD[:40])  # as if max_tokens cut the answer
        self.assertEqual(cm.exception.errors()[0]["type"], "json_invalid")

    def test_duplicate_keys_last_one_wins(self):
        # Documented behaviour: the second "priority" silently replaces the first.
        t = extract.Ticket.model_validate_json(
            '{"category": "bug", "priority": 1, "priority": 5, "summary": "x", "needs_human": true}')
        self.assertEqual(t.priority, 5)

    def test_schema_matches_the_rules(self):
        s = extract.Ticket.model_json_schema()
        self.assertEqual(s["properties"]["category"]["enum"], ["billing", "bug", "feature", "other"])
        self.assertEqual((s["properties"]["priority"]["minimum"], s["properties"]["priority"]["maximum"]), (1, 5))
        self.assertIs(s["additionalProperties"], False)
        self.assertEqual(sorted(s["required"]), sorted(["category", "priority", "summary", "needs_human"]))
        json.loads(extract.schema_for_provider())  # it is valid JSON text


class FenceTests(unittest.TestCase):
    def test_strip_fence(self):
        self.assertEqual(extract.strip_fence(f"```json\n{GOOD}\n```"), GOOD)
        self.assertEqual(extract.strip_fence(f"```\n{GOOD}\n```"), GOOD)
        self.assertEqual(extract.strip_fence(f"  {GOOD}  "), GOOD)

    def test_text_around_json_is_not_repaired(self):
        # We do not guess: prose before the JSON is a validation error.
        with self.assertRaises(ValidationError):
            extract.Ticket.model_validate_json(extract.strip_fence("Sure! Here it is: " + GOOD))


class RetryLoopTests(unittest.TestCase):
    def test_first_answer_valid_one_call(self):
        model = FakeModel(GOOD)
        t, attempts = extract.extract(model, "classify: login fails")
        self.assertEqual(attempts, 1)
        self.assertEqual(len(model.calls), 1)

    def test_fenced_answer_is_accepted(self):
        t, attempts = extract.extract(FakeModel(f"```json\n{GOOD}\n```"), "x")
        self.assertEqual((t.category, attempts), ("bug", 1))

    def test_errors_are_sent_back_and_second_answer_is_accepted(self):
        bad = '{"category": "urgent", "priority": 2, "summary": "Login fails", "needs_human": true}'
        model = FakeModel(bad, GOOD)
        t, attempts = extract.extract(model, "classify: login fails")
        self.assertEqual(attempts, 2)
        second_call = model.calls[1]
        self.assertEqual([m["role"] for m in second_call], ["user", "assistant", "user"])
        self.assertEqual(second_call[1]["content"], bad)                 # its own bad answer is shown back
        self.assertIn("category: Input should be", second_call[2]["content"])
        self.assertIn("[literal_error]", second_call[2]["content"])

    def test_feedback_does_not_echo_input_values(self):
        secret = "card 4111 1111 1111 1111"
        bad = json.dumps({"category": secret, "priority": 2, "summary": "x", "needs_human": True})
        model = FakeModel(bad, GOOD)
        extract.extract(model, "x")
        self.assertNotIn("4111", model.calls[1][2]["content"])           # only our own copy of the answer has it

    def test_gives_up_after_max_attempts(self):
        model = FakeModel("not json", "still not json", "{}")
        with self.assertRaises(extract.StructuredOutputError) as cm:
            extract.extract(model, "x", max_attempts=3)
        self.assertEqual(cm.exception.attempts, 3)
        self.assertEqual(len(model.calls), 3)                            # bounded: never an endless loop


if __name__ == "__main__":
    unittest.main()
