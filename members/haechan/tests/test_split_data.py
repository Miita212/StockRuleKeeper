"""V-2 분할 코드 시험: 묶음 유지, 중복·충돌, 평가 격리, 재현성, 분할 뒤 겹침 검사."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

import split_data as sd  # noqa: E402


def rec(typ, user, answer="A", **extra):
    r = {"type": typ, "messages": [{"role": "user", "content": user}, {"role": "assistant", "content": answer}]}
    r.update(extra)
    return r


def pool(n=60):
    """시드 n개 + 각 시드의 변형 3개 (변형은 prompt_id 'S1B-<시드 id>')."""
    rows = []
    for i in range(n):
        sid = f"H4a-{i:03d}"
        rows.append(rec("SEED", f"시드 문장 번호 {i} 입니다", f"ans{i}", seed_id=sid))
        for k in range(3):
            rows.append(rec("S1", f"변형 {k} 시드 {i} 다른 말", f"ans{i}", prompt_id=f"S1B-{sid}"))
    return rows


class GroupKey(unittest.TestCase):
    def test_seed_and_variants_share_group(self):
        self.assertEqual(sd.group_key(rec("SEED", "a", seed_id="H4a-001")), "H4a-001")
        self.assertEqual(sd.group_key(rec("S1", "b", prompt_id="S1B-H4a-001")), "H4a-001")

    def test_other_prompt_id_and_text(self):
        self.assertEqual(sd.group_key(rec("S1", "b", prompt_id="S1V-01-엄격")), "S1V-01-엄격")
        self.assertTrue(sd.group_key(rec("S1", "문장")).startswith("txt:"))


class CleanPool(unittest.TestCase):
    def test_exact_duplicate_removed(self):
        kept, dropped = sd.clean_pool([rec("S1", "빚 많은 회사", "A"), rec("S1", "빚  많은 회사!", "A")])
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped[0]["reason"], "duplicate")

    def test_conflict_counted(self):
        kept, dropped = sd.clean_pool([rec("S1", "빚 많은 회사", "A"), rec("S1", "빚 많은 회사", "B")])
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped[0]["reason"], "conflict")

    def test_text_types_may_have_different_answers(self):
        kept, dropped = sd.clean_pool([rec("S7", "확정: 부채비율 100%", "문장 하나"), rec("S7", "확정: 부채비율 100%", "다른 문장"),
                                       rec("S7", "확정: 부채비율 100%", "문장 하나")])
        self.assertEqual(len(kept), 2)
        self.assertEqual([d["reason"] for d in dropped], ["duplicate"])

    def test_same_input_text_types_stay_in_one_split(self):
        rows = [rec("S7", "확정: 입력 가", f"설명 {i}") for i in range(4)] + [rec("S7", f"확정: 입력 {n}", "x") for n in range(20)]
        splits, _, report = sd.run(rows, [])
        self.assertEqual(report["겹침 검사"], "통과(분할 사이 겹침 0건)")
        where = {name for name, v in splits.items() if any(r["messages"][0]["content"] == "확정: 입력 가" for r in v)}
        self.assertEqual(len(where), 1)

    def test_first_file_wins(self):
        kept, _ = sd.clean_pool([rec("SEED", "같은 말", "A", seed_id="s"), rec("S1", "같은 말", "A")])
        self.assertEqual(kept[0]["type"], "SEED")

    def test_bad_record_dropped(self):
        kept, dropped = sd.clean_pool([{"_parse_error": "x"}, {"foo": 1}])
        self.assertEqual(kept, [])
        self.assertEqual({d["reason"] for d in dropped}, {"invalid_format"})


class EvalIsolation(unittest.TestCase):
    def test_pass(self):
        kept, dropped = sd.isolate_from_eval([rec("S1", "빚 적은 회사만 보여줘")], [rec("EVAL", "적자 나는 회사 빼줘")])
        self.assertEqual((len(kept), len(dropped)), (1, 0))

    def test_exact_text(self):
        kept, dropped = sd.isolate_from_eval([rec("S1", "빚 적은 회사만 보여줘")], [rec("EVAL", "빚 적은 회사만, 보여줘!")])
        self.assertEqual(dropped[0]["reason"], "eval_leak_exact")

    def test_same_seed_id(self):
        kept, dropped = sd.isolate_from_eval([rec("SEED", "서로 다른 문장 하나", seed_id="x1")],
                                             [rec("EVAL", "완전히 달라 보이는 말입니다", seed_id="x1")])
        self.assertEqual(dropped[0]["reason"], "eval_leak_seed")

    def test_near_duplicate(self):
        kept, dropped = sd.isolate_from_eval([rec("S1", "빚 많은 회사는 피하고 싶어요 정말로")],
                                             [rec("EVAL", "빚 많은 회사는 피하고 싶어요 정말")], 0.8)
        self.assertEqual(dropped[0]["reason"], "eval_leak_near")


class Split(unittest.TestCase):
    def test_groups_stay_together_and_no_leak(self):
        splits, _, report = sd.run(pool(), [])
        self.assertEqual(report["겹침 검사"], "통과(분할 사이 겹침 0건)")
        for name, rows in splits.items():
            for r in rows:
                self.assertTrue(r["messages"])
        sizes = {k: len(v) for k, v in splits.items()}
        self.assertEqual(sum(sizes.values()), 240)
        self.assertTrue(sizes["train"] > sizes["valid"] > 0 and sizes["test"] > 0)

    def test_ratio_roughly_8_1_1(self):
        splits, _, _ = sd.run(pool(100), [])
        total = sum(len(v) for v in splits.values())
        self.assertAlmostEqual(len(splits["train"]) / total, 0.8, delta=0.08)

    def test_deterministic(self):
        a, _, _ = sd.run(pool(), [], random_seed=7)
        b, _, _ = sd.run(pool(), [], random_seed=7)
        c, _, _ = sd.run(pool(), [], random_seed=8)
        key = lambda s: [sd.vd.user_key(r) for r in s["valid"]]  # noqa: E731
        self.assertEqual(key(a), key(b))
        self.assertNotEqual(key(a), key(c))

    def test_with_eval_test_is_eval_and_pool_only_train_valid(self):
        ev = [rec("EVAL", f"평가 전용 질문 {i} 번입니다") for i in range(10)]
        splits, _, report = sd.run(pool(), ev)
        self.assertEqual(len(splits["test"]), 10)
        self.assertTrue(all(r["type"] == "EVAL" for r in splits["test"]))
        self.assertTrue(all(r["type"] != "EVAL" for r in splits["train"] + splits["valid"]))
        self.assertEqual(report["경고"], [])

    def test_no_eval_warns(self):
        _, _, report = sd.run(pool(10), [])
        self.assertTrue(report["경고"])

    def test_eval_leak_dropped_from_pool(self):
        p = pool(20)
        ev = [rec("EVAL", p[0]["messages"][0]["content"])]  # 풀의 첫 문장과 같은 평가 문장
        splits, dropped, _ = sd.run(p, ev)
        self.assertIn("eval_leak_exact", {d["reason"] for d in dropped})
        texts = {sd.vd.user_key(r) for r in splits["train"] + splits["valid"]}
        self.assertNotIn(sd.vd.user_key(ev[0]), texts)

    def test_every_type_reaches_valid(self):
        rows = pool(30) + [rec("S6", f"용어 질문 {i} 번째 입니다", prompt_id=f"S6-{i}") for i in range(30)]
        splits, _, _ = sd.run(rows, [])
        self.assertIn("S6", {r["type"] for r in splits["valid"]})
        self.assertIn("S1", {r["type"] for r in splits["valid"]} | {r["type"] for r in splits["train"]})

    def test_tiny_stratum_goes_to_train(self):
        splits, _, _ = sd.run([rec("S9", "하나뿐인 유형 문장", prompt_id="p1")], [])
        self.assertEqual(len(splits["train"]), 1)


class LeakCheck(unittest.TestCase):
    def test_detects_injected_group_leak(self):
        splits = {"train": [rec("S1", "문장 가", prompt_id="S1B-k1")], "test": [rec("S1", "문장 나", prompt_id="S1B-k1")]}
        self.assertTrue(sd.leak_check(splits))

    def test_detects_injected_text_leak(self):
        splits = {"train": [rec("S1", "같은 문장")], "test": [rec("S1", "같은  문장!")]}
        self.assertTrue(sd.leak_check(splits))

    def test_clean_passes(self):
        splits = {"train": [rec("S1", "문장 가")], "test": [rec("S1", "문장 나")]}
        self.assertEqual(sd.leak_check(splits), [])


class EndToEnd(unittest.TestCase):
    def test_cli(self):
        tmp = Path(tempfile.mkdtemp())
        sd.write_jsonl(tmp / "pool.jsonl", pool(20))
        sd.write_jsonl(tmp / "eval.jsonl", [rec("EVAL", f"평가 문장 {i} 입니다 정말") for i in range(5)])
        code = sd.main(["--pool", str(tmp / "pool.jsonl"), "--eval", str(tmp / "eval.jsonl"), "--out", str(tmp / "out")])
        self.assertEqual(code, 0)
        for f in ("train.jsonl", "valid.jsonl", "test.jsonl", "dropped.jsonl", "split_report.json"):
            self.assertTrue((tmp / "out" / f).exists(), f)
        report = json.loads((tmp / "out" / "split_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["분할"]["test"], 5)


if __name__ == "__main__":
    unittest.main()
