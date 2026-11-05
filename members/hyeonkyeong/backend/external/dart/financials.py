"""DART 단일회사 전체 재무제표를 내부 스키마로 바꿔 돌려준다.

내부 스키마: {"basis": "CFS"|"OFS", "rows": [{sj_div, account_id, account_name,
              current, current_cum, prev, prev_cum, prev_q}]}  (금액은 원 단위 숫자, 없으면 None)
- 연결(CFS)을 우선 받고 데이터가 없으면 별도(OFS)로 폴백한다. 어느 쪽을 썼는지 basis에 남긴다.
- reprt_code: 11013(1분기) 11012(반기) 11014(3분기) 11011(사업보고서)
- with_xbrl=True이면 현금흐름표에 감가상각비 행이 없는 기업(삼성전자·SK하이닉스 등, 상각비가 주석에만 있음)의 상각비를
  공시 XBRL 원본(fnlttXbrl)에서 찾아 CF 행으로 덧붙인다. 보고서마다 zip 하나를 받으므로 필요한 보고서에만 켠다.
"""
import io
import re
import zipfile
from datetime import datetime

import config
from external.dart.client import get_bytes, get_json
from external.fixtures import load


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _fetch(corp_code: str, year: int, reprt_code: str, fs_div: str):
    """(행 목록, 접수번호). 데이터가 없으면 (None, None)."""
    res = get_json("fnlttSinglAcntAll.json", {
        "corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": fs_div,
    })
    if res.get("status") == "013":  # 조회된 데이터 없음
        return None, None
    if res.get("status") != "000":
        raise RuntimeError(f"DART 오류 {res.get('status')} {res.get('message')}")
    rows = [{
        "sj_div": r.get("sj_div"),
        "account_id": r.get("account_id"),
        "account_name": r.get("account_nm"),
        "current": _num(r.get("thstrm_amount")),
        "current_cum": _num(r.get("thstrm_add_amount")),
        "prev": _num(r.get("frmtrm_amount")),
        "prev_cum": _num(r.get("frmtrm_add_amount")),
        "prev_q": _num(r.get("frmtrm_q_amount")),  # 현금흐름표는 전년 동기 누적이 여기에 온다(실응답 확인)
    } for r in res.get("list", [])]
    return rows, (res.get("list") or [{}])[0].get("rcept_no")


# ---- XBRL 보완: 상각비 ----
XBRL_CONCEPTS = {  # XBRL 개념 -> (CF 행의 account_id, 이름)
    "ifrs-full:AdjustmentsForDepreciationExpense": ("ifrs-full_AdjustmentsForDepreciationExpense", "감가상각비"),
    "ifrs-full:AdjustmentsForAmortisationExpense": ("ifrs-full_AdjustmentsForAmortisationExpense", "무형자산상각비"),
    "dart:AdjustmentsForDepreciationRightofuseAssets": ("dart_AdjustmentsForDepreciationRightofuseAssets", "사용권자산상각비"),
}
CS_AXIS = "ifrs-full:ConsolidatedAndSeparateFinancialStatementsAxis"
CS_MEMBER = {"CFS": "ifrs-full:ConsolidatedMember", "OFS": "ifrs-full:SeparateMember"}
REPORTED_AXIS = "ifrs-full:CarryingAmountAccumulatedDepreciationAmortisationAndImpairmentAndGrossCarryingAmountAxis"
REPORTED = "dart:ReportedAmountMember"  # 상각비 값에 붙는 보조 축(총계 의미)


def _pick(items, basis):
    """연결/별도 축과 보조 축만 가진 값 중 (당기 누적, 전년 동기 누적). 없으면 (None, None)."""
    ok = []
    for start, end, value, members in items:
        axes = dict(m.split("=", 1) for m in members)
        cs = axes.pop(CS_AXIS, None)
        if axes.get(REPORTED_AXIS) == REPORTED:
            axes.pop(REPORTED_AXIS)
        if not axes and cs in (CS_MEMBER[basis], None):
            ok.append((datetime.fromisoformat(start), datetime.fromisoformat(end), value))
    if not ok:
        return None, None
    end = max(e for _, e, _ in ok)
    cur = max((x for x in ok if x[1] == end), key=lambda x: x[1] - x[0])
    prev = [x for x in ok if abs((end - x[1]).days - 365) <= 5]
    return cur[2], (max(prev, key=lambda x: x[1] - x[0])[2] if prev else None)


def _xbrl_rows(rcept_no: str, reprt_code: str, basis: str, have_ids: set) -> list[dict]:
    """현금흐름표에 없는 상각비를 XBRL에서 찾아 CF 행으로 돌려준다."""
    todo = [c for c, (aid, _) in XBRL_CONCEPTS.items() if aid not in have_ids]
    if not todo or not rcept_no:
        return []
    content = get_bytes("fnlttXbrl.xml", {"rcept_no": rcept_no, "reprt_code": reprt_code})
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
        text = zf.read(next(n for n in zf.namelist() if n.endswith(".xbrl"))).decode("utf-8")
    except (zipfile.BadZipFile, StopIteration):  # 오류 응답(JSON/XML)이 온 경우: 보완하지 않는다
        return []
    contexts = {}
    for m in re.finditer(r'<(?:\w+:)?context id="([^"]+)">(.*?)</(?:\w+:)?context>', text, re.S):
        period = re.search(r"<(?:\w+:)?startDate>([^<]+)<.*?<(?:\w+:)?endDate>([^<]+)<", m.group(2), re.S)
        if period:  # 기간 컨텍스트만(시점은 재무상태표용)
            members = [f"{a}={b}" for a, b in re.findall(r'dimension="([^"]+)">([^<]+)<', m.group(2))]
            contexts[m.group(1)] = [*period.groups(), members]
    out = []
    for concept in todo:
        items = [[*contexts[m.group(1)][:2], float(m.group(2)), contexts[m.group(1)][2]]
                 for m in re.finditer(rf'<{re.escape(concept)}\s[^>]*?contextRef="([^"]+)"[^>]*>([^<]+)<', text)
                 if m.group(1) in contexts]
        cur, prev = _pick(items, basis)
        if cur is None:
            continue
        aid, name = XBRL_CONCEPTS[concept]
        annual = reprt_code == "11011"  # 사업보고서는 전기 값이 prev, 그 외는 전년 동기 누적이 prev_q (현금흐름표와 같은 자리)
        out.append({"sj_div": "CF", "account_id": aid, "account_name": name, "current": cur, "current_cum": None,
                    "prev": prev if annual else None, "prev_cum": None, "prev_q": None if annual else prev})
    return out


def get_statement(corp_code: str, year: int, reprt_code: str, with_xbrl: bool = False) -> dict | None:
    if config.EXTERNAL_MODE == "fixture":
        return load("dart_statement.json")
    order = ["CFS", "OFS"] if config.DART_CONSOLIDATED_FIRST else ["OFS", "CFS"]
    for basis in order:
        rows, rcept_no = _fetch(corp_code, year, reprt_code, basis)
        if rows:
            if with_xbrl:
                rows += _xbrl_rows(rcept_no, reprt_code, basis, {r["account_id"] for r in rows if r["sj_div"] == "CF"})
            return {"basis": basis, "rows": rows}
    return None
