"""지표 계산·판정 검증(외부 호출 없음). 사용: python scripts/test_indicators.py"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indicators.calc_financial import compute_financial_indicators  # noqa: E402
from indicators.calc_price import compute_price_indicators  # noqa: E402
from indicators.judge import judge_stock  # noqa: E402
from indicators.master import MASTER, actual_text, criterion_text  # noqa: E402


def row(sj, aid, name, cur, cum=None, prev=None, prev_cum=None, prev_q=None):
    return {"sj_div": sj, "account_id": aid, "account_name": name,
            "current": cur, "current_cum": cum, "prev": prev, "prev_cum": prev_cum, "prev_q": prev_q}


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


def annual_report(oi, oi_prev, finance_cost):
    return {(2024, "11011"): {"basis": "CFS", "rows": [
        row("CIS", "dart_OperatingIncomeLoss", "영업이익", oi, prev=oi_prev),
        row("CIS", "ifrs-full_FinanceCosts", "금융비용", finance_cost, prev=1.0)]}}


def test_edge_cases():
    as_of = date(2025, 6, 1)
    # 금융비용이 0: 영업이익 흑자면 충족(이자 부담 없음), 적자면 계산하지 않는다
    free = compute_financial_indicators(annual_report(20.0, 10.0, 0.0), as_of)
    assert free[3]["value"] == 100.0 and free[3]["no_cost"]
    row3 = judge_stock([{"id": 3, "operator": ">=", "value": 3}], {3: free[3]})["rows"][0]
    assert row3["pass"] and row3["actual"] == "이자 부담 없음"
    loss = compute_financial_indicators(annual_report(-20.0, 10.0, 0.0), as_of)
    assert loss[3]["value"] is None and loss[3]["reason"] == "영업적자"
    # 금융비용을 음수로 적는 회사: 크기로 읽는다 (20 / 4 = 5)
    neg = compute_financial_indicators(annual_report(20.0, 10.0, -4.0), as_of)
    assert neg[3]["value"] == 5.0 and not neg[3].get("no_cost")
    # 12개월 합이 0 이하(환율손실 되돌림): 직전 사업연도 값으로 대신한다 (한미반도체 2026 반기와 같은 모양)
    fx = {(2025, "11012"): {"basis": "CFS", "rows": [
        row("CIS", "dart_OperatingIncomeLoss", "영업이익", 8.0, cum=18.0, prev=4.0, prev_cum=9.0),
        row("CIS", "ifrs-full_FinanceCosts", "금융원가", 8.9, cum=26.8, prev=113.6, prev_cum=192.1)]},
        (2024, "11011"): {"basis": "CFS", "rows": [
        row("CIS", "dart_OperatingIncomeLoss", "영업이익", 20.0), row("CIS", "ifrs-full_FinanceCosts", "금융원가", 103.1)]}}
    f = compute_financial_indicators(fx, date(2025, 9, 1))[3]  # 영업이익 29, 금융비용 103+26.8-192.1 < 0 -> 103.1
    assert abs(f["value"] - 29.0 / 103.1) < 1e-9 and not f.get("no_cost")
    # 현금흐름표에 상각비가 있으면 EBITDA로 정확히 계산한다: (20 + 10 + 5) / 5 = 7
    exact = annual_report(20.0, 10.0, 5.0)
    exact[(2024, "11011")]["rows"] += [row("CF", "ifrs-full_AdjustmentsForDepreciationExpense", "감가상각비", 10.0),
                                       row("CF", "ifrs-full_AdjustmentsForAmortisationExpense", "무형자산상각비", 5.0)]
    got = compute_financial_indicators(exact, as_of)[3]
    assert got["value"] == 7.0 and not got["approx"]
    # 반기보고서: 직전 사업연도 + 당기 누적 − 전년 동기 누적 = 10 + 6 − 4 = 12 (감가상각비)
    half = {(2025, "11012"): {"basis": "CFS", "rows": [
        row("CIS", "dart_OperatingIncomeLoss", "영업이익", 8.0, cum=18.0, prev=4.0, prev_cum=9.0),
        row("CIS", "ifrs-full_FinanceCosts", "금융비용", 1.0, cum=2.0, prev=1.0, prev_cum=1.0),
        row("CF", "ifrs-full_AdjustmentsForDepreciationExpense", "감가상각비", 6.0, prev_q=4.0)]}}
    half.update({(2024, "11011"): {"basis": "CFS", "rows": [
        row("CIS", "dart_OperatingIncomeLoss", "영업이익", 20.0), row("CIS", "ifrs-full_FinanceCosts", "금융비용", 3.0),
        row("CF", "ifrs-full_AdjustmentsForDepreciationExpense", "감가상각비", 10.0)]}})
    h = compute_financial_indicators(half, date(2025, 9, 1))[3]  # 영업이익 20+18-9=29, 금융비용 3+2-1=4, 감가 12
    assert h["value"] == (29.0 + 12.0) / 4.0 and not h["approx"]
    # 영업이익 증가율: 적자가 줄어든 것은 증가가 아니다
    shrink = compute_financial_indicators(annual_report(-5.0, -10.0, 1.0), as_of)
    assert shrink[9]["value"] is None and shrink[9]["reason"] == "적자 지속(축소)"
    row9 = judge_stock([{"id": 9, "operator": ">=", "value": 20}], {9: shrink[9]})["rows"][0]
    assert not row9["pass"] and row9["actual"] == "적자 지속(축소)"
    # 연속 배당 연수: 이력이 끝나서 멈추면 "이상", 중간에 끊기면 아니다
    daily = [{"date": f"2025-12-{d:02d}", "close": 100.0, "volume": 1.0, "value": 1.0} for d in range(1, 29)]
    div = [{"record_date": f"{y}-12-31", "amount_per_share": 10.0} for y in range(2020, 2025)]
    assert compute_price_indicators(daily, div, None, date(2025, 12, 31))[13]["at_least"]
    gap = div + [{"record_date": "2018-12-31", "amount_per_share": 10.0}]
    assert not compute_price_indicators(daily, gap, None, date(2025, 12, 31))[13]["at_least"]


if __name__ == "__main__":
    test_financial()
    test_price()
    test_judge()
    test_edge_cases()
    print("OK")
