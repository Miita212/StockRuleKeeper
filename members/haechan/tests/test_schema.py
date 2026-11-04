import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.indicators import INDICATORS  # noqa: E402
from llm.schema import parse_and_validate, validate  # noqa: E402


def ok(conds, **kw):
    base = {"intent": "principle", "needs_clarification": False,
            "question": None, "choices": [], "conditions": conds,
            "unsupported_terms": [], "message": None}
    base.update(kw)
    return base


class SchemaTest(unittest.TestCase):
    def test_indicator_count(self):
        self.assertEqual(len(INDICATORS), 20)

    def test_valid(self):
        self.assertEqual(validate(ok([{"indicator": "PER", "op": "<=", "value": 15}])), [])

    def test_principle_needs_conditions(self):
        self.assertTrue(validate(ok([])))

    def test_unknown_indicator(self):
        self.assertTrue(validate(ok([{"indicator": "ROE", "op": ">", "value": 10}])))

    def test_unrealistic_value(self):
        self.assertTrue(validate(ok([{"indicator": "PER", "op": "<", "value": 99999}])))

    def test_period_required(self):
        self.assertTrue(validate(ok([{"indicator": "PERIOD_RETURN", "op": ">", "value": 5}])))
        self.assertEqual(validate(ok([{"indicator": "PERIOD_RETURN", "op": ">", "value": 5,
                                       "period_months": 3}])), [])

    def test_period_not_allowed(self):
        self.assertTrue(validate(ok([{"indicator": "PER", "op": "<", "value": 10,
                                      "period_months": 3}])))

    def test_clarification(self):
        good = ok([], needs_clarification=True, question="기준이 몇 배인가요?",
                  choices=["PER 10배 이하", "PER 15배 이하"])
        self.assertEqual(validate(good), [])
        self.assertTrue(validate(ok([], needs_clarification=True)))  # question 없음
        bad = dict(good, intent="off_topic", message="안내")
        self.assertTrue(validate(bad))  # 되묻기는 principle만

    def test_not_clarifying_has_no_choices(self):
        self.assertTrue(validate(ok([{"indicator": "PER", "op": "<", "value": 10}],
                                    choices=["a"])))

    def test_off_topic(self):
        self.assertEqual(validate(ok([], intent="off_topic", message="범위 밖이에요")), [])
        self.assertTrue(validate(ok([], intent="off_topic")))  # message 없음
        self.assertTrue(validate(ok([{"indicator": "PER", "op": "<", "value": 10}],
                                    intent="off_topic", message="x")))

    def test_unsupported(self):
        self.assertEqual(validate(ok([], intent="unsupported_indicator",
                                     unsupported_terms=["ROE"], message="지원하지 않아요")), [])
        self.assertTrue(validate(ok([], intent="unsupported_indicator", message="x")))

    def test_app_intents(self):
        for it in ("explain", "manage", "simulate"):
            self.assertEqual(validate(ok([], intent=it)), [], it)

    def test_principle_with_unsupported_part(self):
        self.assertEqual(validate(ok([{"indicator": "PER", "op": "<", "value": 10}],
                                     unsupported_terms=["ROE"])), [])

    def test_bad_json(self):
        obj, errs = parse_and_validate("{not json")
        self.assertIsNone(obj)
        self.assertTrue(errs)


if __name__ == "__main__":
    unittest.main()
