"""한투 시세·배당·종목 분류를 우리 서비스의 내부 스키마로 바꿔 돌려준다.

상위 모듈은 이 파일의 반환 형식만 알면 된다(한투 원본 필드명은 여기 안에서만 쓴다).
EXTERNAL_MODE=fixture 이면 external/fixtures 의 샘플을 돌려준다.

내부 스키마
- snapshot: {code, price, per, pbr, market_cap_won, high_52w, low_52w, from_high_pct, from_low_pct}
- daily:    [{date: 'YYYY-MM-DD', close, volume, value}]  (오래된 날짜 → 최근 순)
- dividend: [{record_date, pay_date, amount_per_share, kind}]
- profile:  {code, industry_code, industry_name, sector_names}
"""
from datetime import date, timedelta

import config
from external.fixtures import load
from external.kis.client import get


def _num(x, default=None):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _iso(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def get_snapshot(code: str) -> dict:
    if config.EXTERNAL_MODE == "fixture":
        return {**load("kis_snapshot.json"), "code": code}
    o = get("/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})["output"]
    return {
        "code": code,
        "price": _num(o.get("stck_prpr")),
        "per": _num(o.get("per")),
        "pbr": _num(o.get("pbr")),
        "market_cap_won": (_num(o.get("hts_avls")) or 0) * 100_000_000,  # 응답 단위: 억원
        "high_52w": _num(o.get("w52_hgpr")),
        "low_52w": _num(o.get("w52_lwpr")),
        "from_high_pct": _num(o.get("w52_hgpr_vrss_prpr_ctrt")),
        "from_low_pct": _num(o.get("w52_lwpr_vrss_prpr_ctrt")),
    }


def get_daily_prices(code: str, start: date, end: date) -> list[dict]:
    """일봉(원주가 기준). 1회 최대 100건이라 구간을 나눠 받는다."""
    if config.EXTERNAL_MODE == "fixture":
        return load("kis_daily.json")
    rows: dict[str, dict] = {}
    cursor = end
    while cursor >= start:
        window_start = max(start, cursor - timedelta(days=140))  # 달력 140일 ≈ 거래일 100건 이내
        res = get("/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", "FHKST03010100", {
            "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": window_start.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": cursor.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "1",
        })
        for r in res.get("output2") or []:
            if r.get("stck_bsop_date"):
                rows[r["stck_bsop_date"]] = {
                    "date": _iso(r["stck_bsop_date"]),
                    "close": _num(r.get("stck_clpr")),
                    "volume": _num(r.get("acml_vol")),
                    "value": _num(r.get("acml_tr_pbmn")),  # 거래대금(원)
                }
        cursor = window_start - timedelta(days=1)
    return [rows[k] for k in sorted(rows)]


def get_dividends(code: str, start: date, end: date) -> list[dict]:
    """예탁원 배당일정으로 주당배당금 이력을 받는다. 조회 가능한 과거 범위는 문서로 확인 필요."""
    if config.EXTERNAL_MODE == "fixture":
        return load("kis_dividends.json")
    res = get("/uapi/domestic-stock/v1/ksdinfo/dividend", "HHKDB669102C0", {
        "CTS": "", "GB1": "0", "F_DT": start.strftime("%Y%m%d"), "T_DT": end.strftime("%Y%m%d"),
        "SHT_CD": code, "HIGH_GB": "",
    })
    out = []
    for r in res.get("output1") or []:
        out.append({
            "record_date": _iso(r["record_date"]) if r.get("record_date") else None,
            "pay_date": _iso(r["divi_pay_dt"].replace("/", "")) if r.get("divi_pay_dt", "").replace("/", "").strip().isdigit() else None,
            "amount_per_share": _num(r.get("per_sto_divi_amt"), 0.0),
            "kind": r.get("divi_kind"),
        })
    return out


def get_profile(code: str) -> dict:
    """종목 기본정보에서 업종·산업분류를 받는다(반도체 종목 선별에 사용)."""
    if config.EXTERNAL_MODE == "fixture":
        return {**load("kis_profile.json"), "code": code}
    o = get("/uapi/domestic-stock/v1/quotations/search-stock-info", "CTPF1002R",
            {"PRDT_TYPE_CD": "300", "PDNO": code})["output"]
    return {
        "code": code,
        "industry_code": o.get("std_idst_clsf_cd"),
        "industry_name": o.get("std_idst_clsf_cd_name"),
        "sector_names": [o.get("idx_bztp_mcls_cd_name"), o.get("idx_bztp_scls_cd_name")],
    }
