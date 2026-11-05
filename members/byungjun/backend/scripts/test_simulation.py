"""시뮬레이션·리포트 검증 (수집된 DB 사용, 만든 원칙은 지운다). 사용: python scripts/test_simulation.py [--report]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from llm.report import check, template  # noqa: E402
from main import app  # noqa: E402


def ind(i, op, v):
    return {"id": i, "operator": op, "value": v, "unit": "", "source": "user", "locked": False}


def test_report_checks():
    sim = {"period_months": 3, "period": {"start": "a", "end": "b"}, "universe": {"name": "반도체 업종", "size": 30},
           "changes": [{"indicator": "부채비율", "before": "100% 이하", "after": "80% 이하"}],
           "before": {"passed_count": 18, "avg_return_pct": 4.2, "up_ratio_pct": 61, "avg_max_drawdown_pct": -9.8},
           "after": {"passed_count": 11, "avg_return_pct": 5.1, "up_ratio_pct": 64, "avg_max_drawdown_pct": -7.4},
           "dropped_stocks": {"count": 7, "avg_return_pct": 2.8, "examples": [{"name": "A", "return_pct": 6.1, "failed_by": "부채비율 91%"}]},
           "added_stocks": {"count": 0, "avg_return_pct": None, "examples": []}, "data_notes": ["기간은 1개 구간만 계산함"]}
    allowed = json.dumps(sim, ensure_ascii=False)
    good = template(sim)
    assert check(good, allowed) == [], check(good, allowed)
    bad = json.loads(json.dumps(good))
    bad["headline"] = "수익률이 9.9%로 더 좋아요 추천"
    problems = check(bad, allowed)
    assert any("숫자" in p for p in problems) and any("금지" in p for p in problems)
    bad2 = json.loads(json.dumps(good)); bad2["comparison"] = []
    assert any("comparison" in p for p in check(bad2, allowed))


def main():
    test_report_checks()
    with TestClient(app) as c:
        a = [ind(1, "<=", 100), ind(19, ">=", 10)]
        pid = c.post("/principles", json={"name": "시뮬 테스트", "indicators": a, "reason": ""}).json()["id"]
        try:
            for months in (3, 6, 12):
                r = c.post("/simulation", json={"principle_id": pid, "months": months, "with_report": False,
                                                "changes": [{"id": 1, "operator": "<=", "value": 30}]}).json()["result"]
                print(f"[{months}개월] 대상 {r['universe']['size']}종목 | 전 {r['before']} | 후 {r['after']}")
                print("   빠진 종목:", r["dropped_stocks"])
                assert r["before"]["passed_count"] >= r["after"]["passed_count"]  # 부채비율을 더 엄격하게 -> 줄거나 같음
            assert c.post("/simulation", json={"principle_id": pid, "months": 5}).status_code == 400
            assert c.post("/simulation", json={"principle_id": 999999, "months": 3}).status_code == 404
            if "--report" in sys.argv:
                out = c.post("/simulation", json={"principle_id": pid, "months": 3,
                                                  "changes": [{"id": 1, "operator": "<=", "value": 30}]}).json()
                print("[리포트 출처]", out["report_source"])
                print(json.dumps(out["report"], ensure_ascii=False, indent=1))
        finally:
            c.delete(f"/principles/{pid}")
    print("OK")


if __name__ == "__main__":
    main()
