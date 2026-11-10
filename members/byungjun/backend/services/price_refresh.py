"""장 마감 뒤 DB 가격 자동 갱신 (서버가 켜져 있는 동안 백그라운드에서 돈다).

- 10분마다 "마지막으로 장이 끝난 날"(평일 15:40 이후면 오늘, 아니면 직전 평일)을 구하고,
  DB 일봉이 그날보다 오래된 종목만 한투에서 일봉·현재가를 받아 저장한다. 배당·재무는 받지 않는다.
- 서버를 켤 때 DB가 오래돼 있어도 바로 따라잡는다. 장중 값은 저장하지 않는다(그날 일봉은 마감 뒤에만).
- 공휴일은 받아 와도 새 날짜가 없으므로, 같은 날짜는 한 번만 시도한다.
- 끄기: .env 에 PRICE_REFRESH=0. 한투를 못 쓰는 모드(fixture, LIVE_FETCH=0)에서도 돌지 않는다.
"""
import json
import threading
import time
from datetime import date, datetime, timedelta

import config
from batch.collect_data import PRICE_DAYS
from db.database import connect
from external.kis import quotes
from services import live
from services import stocks as stock_svc

CLOSE_DONE = (15, 40)   # 이 시각 이후면 그날 종가가 확정됐다고 본다
MARKET_OPEN = (9, 0)
CHECK_SEC = 600

_last_target: date | None = None


def target_date(now: datetime) -> date:
    """DB에 있어야 할 마지막 일봉 날짜."""
    d = now.date()
    if d.weekday() < 5 and (now.hour, now.minute) >= CLOSE_DONE:
        return d
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def in_market_hours(now: datetime) -> bool:
    return now.weekday() < 5 and MARKET_OPEN <= (now.hour, now.minute) < CLOSE_DONE


def refresh(target: date) -> tuple[int, int]:
    """DB 일봉이 target 보다 오래된 종목을 갱신한다. (갱신한 종목 수, 실패 수)"""
    done = failed = 0
    with connect() as conn:
        stale = conn.execute(
            "SELECT s.code, COUNT(p.date) AS n, MAX(p.date) AS last FROM stocks s "
            "LEFT JOIN prices_daily p ON p.code=s.code GROUP BY s.code HAVING last IS NULL OR last < ?",
            (target.isoformat(),)).fetchall()
        for r in stale:
            try:
                start = target - timedelta(days=PRICE_DAYS) if r["n"] < 400 else date.fromisoformat(r["last"])
                rows = [x for x in quotes.get_daily_prices(r["code"], start, target) if x["date"] <= target.isoformat()]
                conn.executemany("INSERT OR REPLACE INTO prices_daily(code,date,close,volume,value) VALUES (?,?,?,?,?)",
                                 [(r["code"], x["date"], x["close"], x["volume"], x["value"]) for x in rows])
                if not in_market_hours(datetime.now()):  # 현재가 스냅샷은 장중이 아닐 때만(= 종가)
                    snap = quotes.get_snapshot(r["code"])
                    conn.execute("INSERT OR REPLACE INTO snapshots(code, fetched_at, json) VALUES (?,?,?)",
                                 (r["code"], datetime.now().isoformat(timespec="seconds"), json.dumps(snap)))
                conn.commit()
                done += 1
            except Exception as e:  # 한 종목 실패는 건너뛰고 다음 확인 때 다시 시도한다
                failed += 1
                print(f"[price_refresh] {r['code']} 실패: {type(e).__name__}: {e}", flush=True)
    stock_svc.clear_cache()  # 03 목록 계산 캐시를 새 가격으로
    return done, failed


def check_once() -> None:
    global _last_target
    target = target_date(datetime.now())
    if target == _last_target:
        return
    t0 = time.time()
    done, failed = refresh(target)
    if failed == 0:
        _last_target = target  # 실패가 있으면 다음 확인 때 남은 종목을 다시 받는다
    if done or failed:
        print(f"[price_refresh] {target} 기준 {done}종목 갱신, 실패 {failed} ({time.time() - t0:.0f}초)", flush=True)


def _loop() -> None:
    while True:
        try:
            check_once()
        except Exception as e:
            print(f"[price_refresh] 확인 실패: {type(e).__name__}: {e}", flush=True)
        time.sleep(CHECK_SEC)


def start() -> None:
    if config.PRICE_REFRESH and live.enabled():
        threading.Thread(target=_loop, name="price_refresh", daemon=True).start()
