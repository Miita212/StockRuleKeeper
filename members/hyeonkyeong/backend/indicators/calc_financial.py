"""재무제표 계열 9개 지표 계산 (DART 데이터). 결과는 {지표 id: {"value", "approx"}}.

계산 기준 (바꾸려면 이 파일 상수·함수 한 곳):
- 재무상태표(부채비율·차입금의존도·자본잠식률): 가장 최근 보고서(분기 또는 사업)의 기말 값.
- 영업이익·매출순이익률: TTM = 직전 사업연도 + 당기 누적 − 전년 동기 누적. 최신 보고서가 사업보고서면 그 연간 값.
- 증가율: 당기 누적 대비 전년 동기 누적 (사업보고서면 당기 연간 대비 전년 연간).
- 연속 영업흑자 연수: 사업보고서의 연간 영업이익을 최근 연도부터 거꾸로, 0 초과인 해를 센다.
- EBITDA/금융비용: (영업이익 + 감가상각비 + 무형자산상각비 + 사용권자산상각비) / 금융비용, 상각비는 현금흐름표 최근 12개월.
  현금흐름표에 감가상각비 계정이 없으면 영업이익/금융비용으로 대체하고 approx=True.
  금융비용은 부호와 상관없이 크기로 읽고, 12개월 합이 0 이하이면 직전 사업연도 값을 쓴다. 금융비용이 0이고 EBITDA가 흑자면 "이자 부담 없음".
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

# 현금흐름표 상각비 계정: (id 목록, 이름 목록)
DEPRECIATION = (["ifrs-full_AdjustmentsForDepreciationExpense"], ["감가상각비", "감가상각비에 대한 조정"])
AMORTIZATION = (["ifrs-full_AdjustmentsForAmortisationExpense"], ["무형자산상각비", "무형자산상각비에 대한 조정"])
RIGHT_OF_USE = (["dart_AdjustmentsForDepreciationRightofuseAssets"], ["사용권자산상각비", "사용권자산상각비에 대한 조정"])
EBITDA_COVER_CAP = 100.0  # 금융비용이 없을 때 EBITDA/금융비용에 넣는 상한값(master RANGES와 같은 100배)
AVAILABLE_FROM ={"11013": (5, 15), "11012": (8, 14), "11014": (11, 14)}  # 사업보고서(11011)는 다음 해 3/31


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


def per_pbr_factors(reports: dict, as_of: date):
    """KIS의 PER·PBR은 직전 결산(사업보고서) 기준이라 최신 실적이 반영되지 않는다.
    보정 비율을 돌려준다: (PER에 곱할 값 = 직전 결산 순이익 / 최근 12개월 순이익,
                         PBR에 곱할 값 = 직전 결산 자본 / 최신 자본). 순이익·자본은 지배주주 귀속분.
    주식 수가 직전 결산 이후 변하지 않았다고 본다(근사). 계산할 수 없으면 (None, None)."""
    key = latest_report(reports, as_of)
    fys = [k for k in reports if k[1] == "11011" and reports[k] and available_date(*k) <= as_of]
    if not key or not fys:
        return None, None
    fy_key = max(fys)
    cur, fy = reports[key]["rows"], reports[fy_key]["rows"]

    def row(rows, ids, sjs):
        return next((r for i in ids for r in rows if r["sj_div"] in sjs and r["account_id"] == i), None)

    ni_ids = ["ifrs-full_ProfitLossAttributableToOwnersOfParent", "ifrs-full_ProfitLoss"]  # 별도재무제표는 앞엣것이 없다
    eq_ids = ["ifrs-full_EquityAttributableToOwnersOfParent", "ifrs-full_Equity"]
    ni_fy, ni_c = row(fy, ni_ids, {"IS", "CIS"}), row(cur, ni_ids, {"IS", "CIS"})
    eq_fy, eq_c = row(fy, eq_ids, {"BS"}), row(cur, eq_ids, {"BS"})
    if not (ni_fy and ni_c and eq_fy and eq_c):
        return None, None
    if key == fy_key:
        ni_ttm = ni_c["current"]
    else:
        ni_ttm = ni_fy["current"] + ni_c["current_cum"] - ni_c["prev_cum"]
    per_factor = ni_fy["current"] / ni_ttm if ni_fy["current"] > 0 and ni_ttm > 0 else None
    pbr_factor = eq_fy["current"] / eq_c["current"] if eq_fy["current"] > 0 and eq_c["current"] > 0 else None
    return per_factor, pbr_factor


def compute_financial_indicators(reports: dict, as_of: date, code: str = "") -> dict:
    out: dict[int, dict] = {}
    key = latest_report(reports, as_of)
    if not key:
        return out
    year, reprt = key
    cur = reports[key]["rows"]
    annual = reprt == "11011"

    def put(i, v, approx=False, **extra):
        out[i] = {"value": v, "approx": approx, **extra}

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

    def cf_ttm(account):
        """현금흐름표 항목의 최근 12개월 = 직전 사업연도 + 당기 누적 − 전년 동기 누적. 못 구하면 None."""
        ids, names = account
        find = lambda rows: next((r for r in rows if r["sj_div"] == "CF" and (r["account_id"] in ids or r["account_name"] in names)), None)
        r = find(cur)
        if not r or r["current"] is None:
            return None
        if annual:
            return r["current"]
        base = reports.get((year - 1, "11011"))
        b = find(base["rows"]) if base else None
        if not b or b["current"] is None or r.get("prev_q") is None:
            return None
        return b["current"] + r["current"] - r["prev_q"]

    def finance_cost_ttm():
        """금융비용 최근 12개월. 비용이므로 부호와 상관없이 크기로 읽는다(음수로 적는 회사가 있다).
        환율손실 되돌림 등으로 12개월 합이 0 이하가 되면 직전 사업연도 연간 값으로 대신한다."""
        r = _find(cur, "finance_cost", {"CIS", "IS"})
        if not r:
            miss("finance_cost")
            return None
        size = lambda v: abs(v) if v is not None else None
        if annual:
            return size(r["current"])
        c = size(r["current_cum"] if r["current_cum"] is not None else r["current"])
        p = size(r["prev_cum"])
        base = reports.get((year - 1, "11011"))
        br = _find(base["rows"], "finance_cost", {"CIS", "IS"}) if base else None
        fy = size(br["current"]) if br else None
        if None in (c, p, fy):
            return None
        ttm = fy + c - p
        return ttm if ttm > 0 else fy

    oi_c, oi_p, oi_ttm = income("oi")
    rev_c, rev_p, rev_ttm = income("revenue")
    _, _, ni_ttm = income("ni")
    fc_ttm = finance_cost_ttm()

    put(5, oi_ttm)
    put(7, ni_ttm / rev_ttm * 100 if ni_ttm is not None and rev_ttm else None)
    put(8, (rev_c - rev_p) / abs(rev_p) * 100 if rev_c is not None and rev_p else None)
    # 영업이익 증가율은 전년이 흑자이고 당기도 0 이상일 때만 계산한다(적자가 줄어든 것을 증가로 보지 않는다)
    if oi_c is None or oi_p is None:
        put(9, None)
    elif oi_p > 0 and oi_c >= 0:
        put(9, (oi_c - oi_p) / oi_p * 100)
    else:
        reason = ("적자 전환" if oi_p > 0 else "흑자 전환" if oi_p < 0 < oi_c else
                  "적자 지속(축소)" if oi_p < 0 and oi_c > oi_p else "적자 지속" if oi_p < 0 else "전년 영업이익 0")
        put(9, None, reason=reason)
    # EBITDA = 영업이익 + 감가상각비 + 무형자산상각비(+사용권자산상각비), 모두 최근 12개월. 상각비는 현금흐름표에서 가져온다.
    # 감가상각비를 못 찾으면(소형주 등) 영업이익으로 대신하고 근사로 표시한다.
    dep = cf_ttm(DEPRECIATION)
    if oi_ttm is not None and dep is not None:
        ebitda, approx = oi_ttm + dep + (cf_ttm(AMORTIZATION) or 0) + (cf_ttm(RIGHT_OF_USE) or 0), False
    else:
        ebitda, approx = oi_ttm, True
    # 금융비용이 0이면 갚을 이자가 없는 것이다: EBITDA가 흑자면 충족(상한값, 화면에는 "이자 부담 없음"), 적자면 계산하지 않는다.
    if ebitda is None or fc_ttm is None:
        put(3, None, approx)
    elif fc_ttm > 0:
        put(3, ebitda / fc_ttm, approx)
    elif ebitda > 0:
        put(3, EBITDA_COVER_CAP, approx, no_cost=True)
    else:
        put(3, None, approx, reason="영업적자")

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
    out[6]["at_least"] = bool(annual_oi) and y < min(annual_oi)  # 적자로 끊긴 게 아니라 이력이 끝나서 멈춘 경우
    return out
