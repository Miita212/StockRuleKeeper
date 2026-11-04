"""지표 계산·판정 검증(외부 호출 없음). 사용: python scripts/test_indicators.py"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indicators.calc_financial import compute_financial_indicators  # noqa: E402
from indicators.calc_price import compute_price_indicators  # noqa: E402
from indicators.judge import judge_stock  # noqa: E402
from indicators.master import MASTER, actual_text, criterion_text  # noqa: E402


def row(sj, aid, name, cur, cum=None, prev=None, prev_cum=None):
    return {"sj_div": sj, "account_id": aid, "account_name": name,
            "current": cur, "current_cum": cum, "prev": prev, "prev_cum": prev_cum}


def test_financial():
    annual = {"basis": "CFS", "rows": [
        row("BS", "ifrs-full_Liabilities", "부채총계", 50.0), row("BS", "ifrs-full_Equity", "자본총계", 100.0),
        row("BS", "ifrs-full_IssuedCapital", "자본금", 10.0), row("BS", "ifrs-full_Assets", "자산총계", 150.0),
        row("BS", "ifrs-full_LongtermBorrowings", "차입금", 15.0),
        row("CIS", "dart_OperatingIncomeLoss", "영업이익", 20.0, prev=10.0),
        row("CIS", "ifrs-full_Revenue", "매출액", 200.0, prev=100.0),
        row("CIS", "ifrs-full_ProfitLoss", "당기순이익", 30.0, prev=5.0),
        row("CIS", "ifrs-full_FinanceCosts", "금융비용", 4.0, prev=3.0)]}
    out = compute_financial_indicators({(2024, "11011"): annual, (2023, "11011"): {"basis": "CFS", "rows": [
        row("CIS", "dart_OperatingIncomeLoss", "영업이익", 10.0, prev=-5.0)]}}, date(2025, 6, 1))
    v = {i: o["value"] for i, o in out.items()}
    assert v[1] == 50.0 and v[2] == 10.0 and v[4] == 0.0
    assert v[5] == 20.0 and v[7] == 15.0 and v[8] == 100.0 and v[9] == 100.0
    assert v[3] == 5.0 and out[3]["approx"]
    assert v[6] == 2.0  # 2024, 2023 흑자 / 2022 적자
    # 사업보고서(2024)는 2025-03-31 이후에만 쓸 수 있다
    assert compute_financial_indicators({(2024, "11011"): annual}, date(2025, 1, 15)) == {}


def test_price():
    daily = [{"date": date.fromordinal(date(2025, 1, 1).toordinal() + i).isoformat(), "close": 100.0 + i,
              "volume": 1000.0, "value": 100000.0} for i in range(300)]
    out = compute_price_indicators(daily, [], None, date(2025, 12, 31))
    v = {i: o["value"] for i, o in out.items()}
    assert v[19] == 100000.0 and v[20] == 1.0 and v[12] == 0.0 and v[13] == 0.0
    assert v[16] == 0.0 and v[17] > 0  # 최고가에서 끝남


def test_judge():
    p = [{"id": 14, "operator": ">=", "value": 1}, {"id": 5, "operator": ">", "value": 0},
         {"id": 16, "operator": ">=", "value": -20}, {"id": 1, "operator": "<=", "value": 100}]
    a = {14: {"value": 5e12}, 5: {"value": -1.0}, 16: {"value": -10.0}, 1: {"value": None}}
    r = judge_stock(p, a)
    assert [x["pass"] for x in r["rows"]] == [True, False, True, False]
    assert r["rows"][3]["actual"] == "데이터 없음"
    assert criterion_text(5, ">", 0) == "흑자" and criterion_text(16, ">=", -20) == "-20% 이내"
    assert actual_text(14, 1.28e15) == "1,280조원" and len(MASTER) == 20


if __name__ == "__main__":
    test_financial()
    test_price()
    test_judge()
    print("OK")
