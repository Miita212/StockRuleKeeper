"""DART 단일회사 전체 재무제표를 내부 스키마로 바꿔 돌려준다.

내부 스키마: {"basis": "CFS"|"OFS", "rows": [{sj_div, account_id, account_name,
              current, current_cum, prev, prev_cum}]}  (금액은 원 단위 숫자, 없으면 None)
- 연결(CFS)을 우선 받고 데이터가 없으면 별도(OFS)로 폴백한다. 어느 쪽을 썼는지 basis에 남긴다.
- reprt_code: 11013(1분기) 11012(반기) 11014(3분기) 11011(사업보고서)
"""
import config
from external.dart.client import get_json
from external.fixtures import load


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _fetch(corp_code: str, year: int, reprt_code: str, fs_div: str) -> list[dict] | None:
    res = get_json("fnlttSinglAcntAll.json", {
        "corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": fs_div,
    })
    if res.get("status") == "013":  # 조회된 데이터 없음
        return None
    if res.get("status") != "000":
        raise RuntimeError(f"DART 오류 {res.get('status')} {res.get('message')}")
    return [{
        "sj_div": r.get("sj_div"),
        "account_id": r.get("account_id"),
        "account_name": r.get("account_nm"),
        "current": _num(r.get("thstrm_amount")),
        "current_cum": _num(r.get("thstrm_add_amount")),
        "prev": _num(r.get("frmtrm_amount")),
        "prev_cum": _num(r.get("frmtrm_add_amount")),
    } for r in res.get("list", [])]


def get_statement(corp_code: str, year: int, reprt_code: str) -> dict | None:
    if config.EXTERNAL_MODE == "fixture":
        return load("dart_statement.json")
    order = ["CFS", "OFS"] if config.DART_CONSOLIDATED_FIRST else ["OFS", "CFS"]
    for basis in order:
        rows = _fetch(corp_code, year, reprt_code, basis)
        if rows:
            return {"basis": basis, "rows": rows}
    return None
