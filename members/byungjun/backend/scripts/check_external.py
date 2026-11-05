"""외부 연동 점검: KIS·DART·LLM을 각각 1회씩 불러 지표별·서비스별 성공/실패를 출력한다.

사용 (backend 폴더에서):
  python scripts/check_external.py             # .env 의 EXTERNAL_MODE 대로
  EXTERNAL_MODE=fixture python scripts/check_external.py   # 키 없이 구조만 확인
키 값은 출력하지 않는다.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from external.dart.corp_codes import fetch_corp_codes  # noqa: E402
from external.dart.financials import get_statement  # noqa: E402
from external.kis import quotes  # noqa: E402
from llm.provider import complete_json  # noqa: E402

CODES = ["005930", "000660"]
SAMPLE_SENTENCE = "빚 많은 회사는 피하고 싶어"


def run(label: str, fn):
    try:
        detail = fn()
        print(f"[성공] {label}: {detail}")
        return True
    except Exception as e:  # 점검 스크립트라 실패해도 다음 항목을 계속 본다
        print(f"[실패] {label}: {type(e).__name__}: {e}")
        return False


def main() -> None:
    # --only kis,dart,llm 으로 점검할 서비스를 고를 수 있다(수집 배치가 한투를 쓰는 동안 dart,llm만 보는 용도)
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else ["kis", "dart", "llm"]
    print(f"모드: EXTERNAL_MODE={config.EXTERNAL_MODE}, KIS_ENV={config.KIS_ENV}, LLM_PROVIDER={config.LLM_PROVIDER}")
    today = date.today()
    results = {}
    for code in CODES if "kis" in only else []:
        results[f"KIS 현재가 {code}"] = run(f"KIS 현재가 {code} (PER·PBR·시총·52주)", lambda: {
            k: v for k, v in quotes.get_snapshot(code).items() if k != "code"})
        results[f"KIS 일봉 {code}"] = run(f"KIS 일봉 {code} (최근 90일)", lambda: (
            lambda d: f"{len(d)}건, {d[0]['date']}~{d[-1]['date']}" if d else "0건")(
            quotes.get_daily_prices(code, today - timedelta(days=90), today)))
        results[f"KIS 배당 {code}"] = run(f"KIS 배당일정 {code} (최근 6년)", lambda: (
            lambda d: f"{len(d)}건, 첫 항목 {d[0] if d else None}")(
            quotes.get_dividends(code, today - timedelta(days=365 * 6), today)))
    corp_map = {}

    def corp():
        for r in fetch_corp_codes():
            corp_map[r["stock_code"]] = r["corp_code"]
        return f"상장사 {len(corp_map)}개 매핑"
    if "dart" in only:
        results["DART corp_code"] = run("DART corpCode.xml", corp)
        for code in CODES:
            cc = corp_map.get(code, "00000000")
            results[f"DART 재무 {code}"] = run(f"DART 재무제표 {code} (직전 사업연도 사업보고서)", lambda: (
                lambda s: "데이터 없음" if not s else f"기준 {s['basis']}, 계정 {len(s['rows'])}개")(
                get_statement(cc, today.year - 1, "11011")))
    if "llm" in only:
        results["LLM"] = run(f"LLM({config.LLM_PROVIDER}) 원칙 문장 변환", lambda: complete_json(
            '사용자의 투자 원칙 문장을 {"summary": "한 줄 요약"} JSON으로만 답하세요.', SAMPLE_SENTENCE,
            sample="llm_principle.json").keys())
    ok = sum(results.values())
    print(f"\n요약: {ok}/{len(results)} 성공")


if __name__ == "__main__":
    main()
