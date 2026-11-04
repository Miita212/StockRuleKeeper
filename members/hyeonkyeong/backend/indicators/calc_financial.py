"""재무제표 계열 9개 지표 계산 (DART 데이터). 결과는 {지표 id: {"value", "approx"}}.

계산 기준 (바꾸려면 이 파일 상수·함수 한 곳):
- 재무상태표(부채비율·차입금의존도·자본잠식률): 가장 최근 보고서(분기 또는 사업)의 기말 값.
- 영업이익·매출순이익률: TTM = 직전 사업연도 + 당기 누적 − 전년 동기 누적. 최신 보고서가 사업보고서면 그 연간 값.
- 증가율: 당기 누적 대비 전년 동기 누적 (사업보고서면 당기 연간 대비 전년 연간).
- 연속 영업흑자 연수: 사업보고서의 연간 영업이익을 최근 연도부터 거꾸로, 0 초과인 해를 센다.
- EBITDA/금융비용: 응답에 감가상각비 계정이 없어(실측) 영업이익/금융비용으로 대체하고 approx=True.
- 매핑 실패(계정을 못 찾음)는 로그에 남기고 해당 지표는 None. 단 차입금은 계정이 없으면 무차입으로 보고 0%(근사)로 한다.
보고서 공시 시점: 1분기 5/15, 반기 8/14, 3분기 11/14, 사업보고서 다음 해 3/31 이후에 쓸 수 있다고 본다.
"""
import logging
from datetime import date

log = logging.getLogger("calc_financial")

# 계정 id (실측: 005930, 000660) — 이름은 id가 없을 때의 보조
ID = {
    "liabilities": ["ifrs-full_Liabilities"], "equity": ["ifrs-full_Equity"],
    "capital": ["ifrs-full_IssuedCapital"],
    "oi": ["dart_OperatingIncomeLoss"], "revenue": ["ifrs-full_Revenue"],
    "ni": ["ifrs-full_ProfitLoss"], "finance_cost": ["ifrs-full_FinanceCosts"],
    "assets": ["ifrs-full_Assets"],
}
NAME = {"liabilities": ["부채총계"], "equity": ["자본총계"], "capital": ["자본금"], "oi": ["영업이익", "영업이익(손실)"],
        "revenue": ["매출액", "수익(매출액)"], "ni": ["당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익"],
        "finance_cost": ["금융비용", "금융원가"], "assets": ["자산총계"]}
BORROWING_IDS = {
    "ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings", "ifrs-full_LongtermBorrowings",
    "ifrs-full_ShorttermBorrowings", "ifrs-full_CurrentBorrowings", "ifrs-full_NoncurrentBorrowings",
    "ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued", "ifrs-full_CurrentPortionOfNoncurrentBondsIssued",
    "ifrs-full_NoncurrentPortionOfNoncurrentLoansReceived", "ifrs-full_CurrentPortionOfNoncurrentLoansReceived",
    "ifrs-full_BondsIssued",
}
BORROWING_NAMES = {"차입금", "단기차입금", "장기차입금", "유동성장기부채", "유동성장기차입금", "사채", "유동성사채"}

AVAILABLE_FROM = {"11013": (5, 15), "11012": (8, 14), "11014": (11, 14)}  # 사업보고서(11011)는 다음 해 3/31


def available_date(year: int, reprt: str) -> date:
    if reprt == "11011":
        return date(year + 1, 3, 31)
    m, d = AVAILABLE_FROM[reprt]
    return date(year, m, d)


def _find(rows, key, sjs):
    for r in rows:
        if r["sj_div"] in sjs and (r["account_id"] in ID[key] or r["account_name"] in NAME[key]):
            return r
    return None


def latest_report(reports: dict, as_of: date):
    """reports: {(year, reprt): statement}. as_of 시점에 쓸 수 있는 가장 최근 보고서의 (year, reprt)."""
    ok = [k for k in reports if reports[k] and available_date(*k) <= as_of]
    return max(ok, key=lambda k: (k[0], {"11013": 1, "11012": 2, "11014": 3, "11011": 4}[k[1]]), default=None)


def compute_financial_indicators(reports: dict, as_of: date, code: str = "") -> dict:
    out: dict[int, dict] = {}
    key = latest_report(reports, as_of)
    if not key:
        return out
    year, reprt = key
    cur = reports[key]["rows"]
    annual = reprt == "11011"

    def put(i, v, approx=False):
        out[i] = {"value": v, "approx": approx}

    def miss(name):
        log.warning("%s: 계정 매핑 실패 %s (%s)", code, name, key)

    def bs(k):
        r = _find(cur, k, {"BS"})
        if not r:
            miss(k)
        return r["current"] if r else None

    liab, eq, cap = bs("liabilities"), bs("equity"), bs("capital")
    put(1, liab / eq * 100 if liab is not None and eq else None)
    put(4, max(0.0, (cap - eq) / cap * 100) if cap and eq is not None else None)

    borrow = [r["current"] for r in cur if r["sj_div"] == "BS" and r["current"] is not None
              and (r["account_id"] in BORROWING_IDS or r["account_name"] in BORROWING_NAMES)]
    assets = bs("assets")
    if borrow:
        put(2, sum(borrow) / assets * 100 if assets else None)
    else:
        # 실측: 무차입 회사는 차입금·사채 계정 자체가 없다. 0으로 보되, 다른 계정에 섞여 있을 수 있어 근사로 표시한다.
        put(2, 0.0 if assets else None, approx=True)

    # 손익: 누적(당기), 전년 동기 누적, TTM
    def income(k):
        r = _find(cur, k, {"CIS", "IS"})
        if not r:
            miss(k)
            return None, None, None
        c = r["current"] if annual else (r["current_cum"] if r["current_cum"] is not None else r["current"])
        p = r["prev"] if annual else r["prev_cum"]
        ttm = c
        if not annual:
            base = reports.get((year - 1, "11011"))
            br = _find(base["rows"], k, {"CIS", "IS"}) if base else None
            ttm = (br["current"] + c - p) if br and br["current"] is not None and c is not None and p is not None else None
        return c, p, ttm

    oi_c, oi_p, oi_ttm = income("oi")
    rev_c, rev_p, rev_ttm = income("revenue")
    _, _, ni_ttm = income("ni")
    fc_c, _, fc_ttm = income("finance_cost")

    put(5, oi_ttm)
    put(7, ni_ttm / rev_ttm * 100 if ni_ttm is not None and rev_ttm else None)
    put(8, (rev_c - rev_p) / abs(rev_p) * 100 if rev_c is not None and rev_p else None)
    put(9, (oi_c - oi_p) / abs(oi_p) * 100 if oi_c is not None and oi_p else None)
    # EBITDA 대신 영업이익/금융비용(근사). 금융비용이 0이면 비율을 정의할 수 없어 None.
    put(3, oi_ttm / fc_ttm if oi_ttm is not None and fc_ttm else None, approx=True)

    # 연속 영업흑자 연수: 사업보고서에서 연도별 영업이익 모으기(당기 + 전기)
    annual_oi: dict[int, float] = {}
    for (y, rc), st in reports.items():
        if rc != "11011" or not st or available_date(y, rc) > as_of:
            continue
        r = _find(st["rows"], "oi", {"CIS", "IS"})
        if r:
            if r["current"] is not None:
                annual_oi[y] = r["current"]
            if r["prev"] is not None:
                annual_oi.setdefault(y - 1, r["prev"])
    last_year = max(annual_oi, default=None)
    streak = 0
    y = last_year
    while y is not None and annual_oi.get(y, 0) > 0:
        streak += 1
        y -= 1
    put(6, float(streak) if last_year is not None else None)
    return out
