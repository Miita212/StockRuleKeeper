"""V-1 검증 코드 시험: 규칙마다 통과 샘플 1개 + 실패 샘플 1개 이상."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

import validate_data as vd  # noqa: E402


def m(iid, name, op, unit, default, lo, hi, allowed=None, definition="", note=""):
    return {"id": iid, "name": name, "operator": op, "allowed_operators": allowed or [op], "unit": unit,
            "default": default, "min": lo, "max": hi, "definition": definition, "note": note, "source": []}


MASTER = {
    1: m(1, "부채비율", "<=", "%", 100, 0, 1000, definition="부채총계 ÷ 자본총계 × 100 (낮을수록 빚 부담이 적어요)"),
    5: m(5, "영업이익", ">", "억원", 0, -100000, 1000000, [">", "<="]),
    6: m(6, "연속 영업흑자 연수", ">=", "년", 3, 0, 30),
    12: m(12, "배당수익률", ">=", "%", 2, 0, 30),
    13: m(13, "연속 배당 연수", ">=", "년", 3, 0, 30),
    16: m(16, "52주 최고가 대비 등락률", ">=", "%", -20, -100, 0, [">=", "<="]),
}


def chat(typ, user, answer, **extra):
    a = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
    rec = {"type": typ, "messages": [{"role": "user", "content": user}, {"role": "assistant", "content": a}]}
    rec.update(extra)
    return rec


def rules(rec):
    return {r for r, _ in vd.validate_record(rec, MASTER)}


GOOD_IND = {"indicators": [{"id": 1, "operator": "<=", "value": 100, "unit": "%", "source": "user"}]}


class V1Format(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(rules(chat("S1", "빚 적은 곳", GOOD_IND)), set())

    def test_json_missing(self):
        self.assertIn("V1", rules(chat("S1", "빚 적은 곳", "그냥 문장이에요")))

    def test_unknown_shape(self):
        self.assertIn("V1", rules(chat("S1", "x", {"foo": 1})))

    def test_bad_messages(self):
        self.assertIn("V1", rules({"type": "S1", "messages": []}))

    def test_clarify_needs_three_options(self):
        bad = {"needs_clarification": True, "reason": "VALUE_MISSING", "indicator_id": 1, "message": "얼마나요?",
               "options": [{"label": "a", "value": 50}, {"label": "b", "value": 100}]}
        self.assertIn("V1", rules(chat("S3", "빚 많은 회사는 싫어", bad)))

    def test_clarify_good(self):
        good = {"needs_clarification": True, "reason": "VALUE_MISSING", "indicator_id": 1, "message": "얼마나요?",
                "options": [{"label": "a", "value": 50}, {"label": "b", "value": 100}, {"label": "c", "value": 200}]}
        self.assertEqual(rules(chat("S3", "빚 많은 회사는 싫어", good)), set())

    def test_refusal_text_allowed_for_s5(self):
        self.assertEqual(rules(chat("S5", "삼성전자 사도 돼?", "저는 종목을 추천하지 않아요. 내 원칙에 맞는지는 판정서에서 확인해요.")), set())

    def test_input_output_format(self):
        self.assertEqual(rules({"type": "S1", "input": "빚 적은 곳", "output": GOOD_IND}), set())

    def test_duplicate_indicator_in_output(self):
        ind = GOOD_IND["indicators"][0]
        self.assertIn("V1", rules(chat("S1", "x", {"indicators": [ind, ind]})))


class V2V3V4Values(unittest.TestCase):
    def ind(self, **kw):
        e = {"id": 1, "operator": "<=", "value": 100, "unit": "%", "source": "user"}
        e.update(kw)
        return chat("S1", "빚", {"indicators": [e]})

    def test_v2_pass_and_fail(self):
        self.assertNotIn("V2", rules(self.ind()))
        self.assertIn("V2", rules(self.ind(id=21)))  # ROE 같은 20개 밖 지표
        self.assertIn("V2", rules(self.ind(id=0)))

    def test_v3_range(self):
        self.assertNotIn("V3", rules(self.ind(value=1000)))
        self.assertIn("V3", rules(self.ind(value=-50)))
        self.assertIn("V3", rules(self.ind(value="100")))

    def test_v4_operator_unit(self):
        self.assertNotIn("V4", rules(self.ind()))
        self.assertIn("V4", rules(self.ind(operator=">=")))
        self.assertIn("V4", rules(self.ind(unit="배")))

    def test_v4_allowed_reverse_operator(self):
        ok = chat("S1", "x", {"indicators": [{"id": 16, "operator": "<=", "value": -30, "unit": "%"}]})
        self.assertNotIn("V4", rules(ok))

    def test_clarify_option_range(self):
        bad = {"needs_clarification": True, "reason": "VALUE_MISSING", "indicator_id": 1, "message": "?",
               "options": [{"label": "a", "value": 50}, {"label": "b", "value": 100}, {"label": "c", "value": 5000}]}
        self.assertIn("V3", rules(chat("S3", "x", bad)))


class V5Locked(unittest.TestCase):
    def test_pass(self):
        out = {"changes": [{"id": 1, "before": 100, "after": 80, "unit": "%"}], "skipped_locked": [6]}
        self.assertEqual(rules(chat("S4", "느슨하게", out, locked=[6])), set())

    def test_changed_locked(self):
        out = {"changes": [{"id": 6, "before": 3, "after": 2, "unit": "년"}]}
        self.assertIn("V5", rules(chat("S4", "느슨하게", out, locked=[6])))

    def test_skipped_not_locked(self):
        out = {"changes": [{"id": 1, "before": 100, "after": 80, "unit": "%"}], "skipped_locked": [13]}
        self.assertIn("V5", rules(chat("S4", "x", out, locked=[6])))


class V6Duplicates(unittest.TestCase):
    def test_pass(self):
        recs = [chat("S1", "빚 적은 곳", GOOD_IND), chat("S1", "빚 많으면 싫어", GOOD_IND)]
        self.assertEqual(vd.check_duplicates(recs), {})

    def test_duplicate(self):
        recs = [chat("S1", "빚 적은 곳", GOOD_IND), chat("S1", "빚  적은 곳!", GOOD_IND)]
        self.assertIn(1, vd.check_duplicates(recs))

    def test_conflict(self):
        other = {"indicators": [{"id": 1, "operator": "<=", "value": 50, "unit": "%"}]}
        recs = [chat("S1", "빚 적은 곳", GOOD_IND), chat("S1", "빚 적은 곳", other)]
        self.assertIn("충돌", vd.check_duplicates(recs)[1][0][1])

    def test_text_types_may_differ(self):
        a = chat("S7", "확정: 부채비율 100%", "빚 걱정을 줄이려고 100%로 잡았어요")
        b = chat("S7", "확정: 부채비율 100%", "빚 부담을 줄이려고 100%로 잡았어요")
        self.assertEqual(vd.check_duplicates([a, b]), {})

    def test_repeat_three_times(self):
        recs = [chat("S1", "빚 적은 곳", GOOD_IND)] * 3
        self.assertEqual(sorted(vd.check_duplicates(recs)), [1, 2])


class V7Forbidden(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(rules(chat("S5", "삼성전자 사도 돼?", "저는 종목을 추천하지 않아요.")), set())

    def test_fail(self):
        for bad in ["이 종목 사세요", "반드시 오릅니다", "무조건 좋아요", "내일은 오를 거예요", "추천드려요"]:
            self.assertIn("V7", rules(chat("S5", "x", bad)), bad)


class V8Report(unittest.TestCase):
    INPUT = '입력: {"period":"3개월","diff":[{"name":"부채비율","before":100,"after":80,"unit":"%"}],"count":{"before":18,"after":11}}'

    def rec(self, text):
        return {"type": "S8", "messages": [{"role": "user", "content": self.INPUT},
                                           {"role": "assistant", "content": text}]}

    def test_pass(self):
        self.assertEqual(rules(self.rec("부채비율을 100%에서 80%로 바꿔서 종목이 18개에서 11개로 줄었어요")), set())

    def test_fail(self):
        self.assertIn("V8", rules(self.rec("종목이 12개로 줄었어요")))


class V9EvalIsolation(unittest.TestCase):
    def test_pass(self):
        train = [chat("S1", "빚 적은 곳", GOOD_IND)]
        ev = [chat("S1", "적자 회사는 빼줘", GOOD_IND)]
        self.assertEqual(vd.check_eval_isolation(train, ev), {})

    def test_same_text(self):
        train = [chat("S1", "빚 적은 곳", GOOD_IND)]
        ev = [chat("S1", "빚 적은 곳!", GOOD_IND)]
        self.assertIn(0, vd.check_eval_isolation(train, ev))

    def test_same_seed(self):
        train = [chat("S1", "빚 적은 곳", GOOD_IND, seed_id="s1")]
        ev = [chat("S1", "다른 문장", GOOD_IND, seed_id="s1")]
        self.assertIn(0, vd.check_eval_isolation(train, ev))


class V10Facts(unittest.TestCase):
    def rec(self, text):
        return {"type": "S7", "indicator_ids": [1], "messages": [
            {"role": "user", "content": "부채비율 100% 이하로 확정"},
            {"role": "assistant", "content": text}]}

    def test_pass(self):
        self.assertEqual(rules(self.rec("빚 걱정을 줄이려고 부채비율을 100% 이하로 잡았어요.")), set())

    def test_invented_average(self):
        self.assertIn("V10", rules(self.rec("업종 평균이 150% 안팎이라 보수적인 기준이에요.")))

    def test_generic_one_is_ignored(self):
        self.assertEqual(rules(self.rec("1년에 버는 돈에 비해 부채비율 100% 이하로 잡았어요.")), set())

    def test_jo_converted_to_eok(self):
        master = dict(MASTER)
        master[14] = m(14, "시가총액", ">=", "억원", 10000, 0, 10000000)
        rec = {"type": "S7", "indicator_ids": [14], "messages": [
            {"role": "user", "content": "시가총액 확정"},
            {"role": "assistant", "content": "시가총액을 1조원 이상으로 잡았어요."}]}
        self.assertEqual(vd.validate_record(rec, master), [])
        rec["messages"][1]["content"] = "시가총액을 3조원 이상으로 잡았어요."
        self.assertTrue(vd.validate_record(rec, master))

    def test_unknown_number(self):
        self.assertIn("V10", rules(self.rec("부채비율을 73% 이하로 잡았어요.")))


class EndToEnd(unittest.TestCase):
    def test_validate_all_and_cli(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        (tmp / "H1_indicator_master_a.json").write_text(json.dumps(list(MASTER.values()), ensure_ascii=False), encoding="utf-8")
        good = chat("S1", "빚 적은 곳", GOOD_IND)
        bad = chat("S1", "ROE 높은 곳", {"indicators": [{"id": 21, "operator": ">=", "value": 15, "unit": "%"}]})
        (tmp / "in.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [good, bad]) + "\nnot json\n",
                                       encoding="utf-8")
        code = vd.main(["--master-dir", str(tmp), "--input", str(tmp / "in.jsonl"),
                        "--out-pass", str(tmp / "p.jsonl"), "--out-fail", str(tmp / "f.jsonl")])
        self.assertEqual(code, 1)
        self.assertEqual(len((tmp / "p.jsonl").read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(len((tmp / "f.jsonl").read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
