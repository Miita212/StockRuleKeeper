"""반도체 종목 풀(stocks 표)의 시세·배당·재무 데이터를 미리 받아 SQLite에 저장한다.

앱이 요청할 때는 외부 API를 부르지 않고 이 저장분만 읽는다. 재무는 분기마다만 바뀐다.
이어받기: 이미 받은 종목·항목은 건너뛴다(--force 로 다시 받기).

사용 (backend 폴더에서):
  python batch/collect_data.py                     # 전체(한투 약 10분 + DART 약 10분)
  python batch/collect_data.py --codes 005930 000660
  python batch/collect_data.py --only kis|dart
"""
import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from db.database import connect, init_db  # noqa: E402
from external.dart.corp_codes import fetch_corp_codes  # noqa: E402
from external.dart.financials import get_statement  # noqa: E402
from external.kis import quotes  # noqa: E402

PRICE_DAYS = 760        # 시뮬레이션(최대 12개월) + 52주 계산에 필요한 일봉 길이
DIVIDEND_YEARS = 8
ERRORS = config.ROOT / ".cache" / "collect_errors.json"


def collect_kis(conn, code: str, force: bool) -> None:
    today = date.today()
    have = conn.execute("SELECT COUNT(*), MAX(date) FROM prices_daily WHERE code=?", (code,)).fetchone()
    if force or have[0] < 400 or have[1] < (today - timedelta(days=5)).isoformat():
        start = today - timedelta(days=PRICE_DAYS) if force or have[0] < 400 else date.fromisoformat(have[1])
        rows = quotes.get_daily_prices(code, start, today)
        conn.executemany("INSERT OR REPLACE INTO prices_daily(code,date,close,volume,value) VALUES (?,?,?,?,?)",
                         [(code, r["date"], r["close"], r["volume"], r["value"]) for r in rows])
    snap = quotes.get_snapshot(code)
    conn.execute("INSERT OR REPLACE INTO snapshots(code, fetched_at, json) VALUES (?,?,?)",
                 (code, datetime.now().isoformat(timespec="seconds"), json.dumps(snap)))
    divs = quotes.get_dividends(code, today - timedelta(days=365 * DIVIDEND_YEARS), today)
    conn.executemany(
        "INSERT OR REPLACE INTO dividends(code,record_date,pay_date,amount_per_share,kind) VALUES (?,?,?,?,?)",
        [(code, d["record_date"], d["pay_date"], d["amount_per_share"], d["kind"]) for d in divs if d["record_date"]])


def report_targets(today: date) -> list[tuple[int, str]]:
    """받을 보고서: 사업보고서 직전 4개 연도 + 올해·작년 분기/반기 보고서."""
    out = [(today.year - k, "11011") for k in range(1, 5)]
    for y in (today.year, today.year - 1):
        out += [(y, "11013"), (y, "11012"), (y, "11014")]
    return out


def collect_dart(conn, code: str, force: bool) -> None:
    row = conn.execute("SELECT corp_code FROM corp_codes WHERE stock_code=?", (code,)).fetchone()
    if not row:
        raise RuntimeError("corp_code 매핑 없음")
    have = {(r[0], r[1]) for r in conn.execute("SELECT year, reprt_code FROM financials WHERE code=?", (code,))}
    for year, reprt in report_targets(date.today()):
        if (year, reprt) in have and not force:
            continue
        st = get_statement(row["corp_code"], year, reprt)
        if st:
            conn.execute("INSERT OR REPLACE INTO financials(code,year,reprt_code,basis,rows_json) VALUES (?,?,?,?,?)",
                         (code, year, reprt, st["basis"], json.dumps(st["rows"], ensure_ascii=False)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", nargs="+")
    ap.add_argument("--only", choices=["kis", "dart"])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    init_db()
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM corp_codes LIMIT 1").fetchone():
            conn.executemany("INSERT OR REPLACE INTO corp_codes(stock_code,corp_code,corp_name) VALUES (?,?,?)",
                             [(r["stock_code"], r["corp_code"], r["corp_name"]) for r in fetch_corp_codes()])
            conn.commit()
        codes = args.codes or [r[0] for r in conn.execute("SELECT code FROM stocks ORDER BY code")]
        errors = json.loads(ERRORS.read_text(encoding="utf-8")) if ERRORS.exists() else {}
        for i, code in enumerate(codes, 1):
            for name, fn in (("kis", collect_kis), ("dart", collect_dart)):
                if args.only and args.only != name:
                    continue
                try:
                    fn(conn, code, args.force)
                    errors.pop(f"{name}:{code}", None)
                except Exception as e:  # 한 종목이 실패해도 다음 종목으로 간다
                    errors[f"{name}:{code}"] = f"{type(e).__name__}: {e}"
            conn.commit()
            if i % 5 == 0 or i == len(codes):
                ERRORS.parent.mkdir(exist_ok=True)
                ERRORS.write_text(json.dumps(errors, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"{i}/{len(codes)} 실패 {len(errors)}건", flush=True)
            time.sleep(0)  # 호출 간격은 각 어댑터의 Throttle이 지킨다


if __name__ == "__main__":
    main()
