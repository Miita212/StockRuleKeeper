"""SQLite DB 백업. 서버나 수집 배치가 DB를 쓰는 중이어도 일관된 스냅샷을 만든다.

WAL 모드라서 .db 파일만 cp 하면 최근 내용이 빠질 수 있다. SQLite 백업 API를 쓴다.

사용 (backend 폴더에서):
  python db/backup.py                    # db/backups/stockrule_날짜_시각.db 생성
  python db/backup.py --label universe   # 파일명에 라벨 추가: stockrule_날짜_시각_universe.db
  python db/backup.py --list             # 백업 목록과 종목 수
  python db/backup.py --keep 10          # 백업 후 오래된 것을 지우고 최근 10개만 남김
복원은 README 대신 아래 두 줄 (백엔드·배치를 먼저 끈 뒤):
  rm -f data/stockrule.db-wal data/stockrule.db-shm
  cp db/backups/<파일>.db data/stockrule.db
백업 폴더(db/backups/)는 .gitignore 대상이다. 커밋하지 않는다.
"""
import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

BACKUP_DIR = Path(__file__).resolve().parent / "backups"
UNIVERSE_JSON = config.ROOT / "data" / "semiconductor_universe.json"
COUNT_TABLES = ["stocks", "prices_daily", "financials", "dividends", "snapshots", "principles"]


def _counts(path: Path) -> dict[str, int]:
    """백업 파일을 읽기 전용으로 열어 표별 건수를 센다."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        out = {}
        for t in COUNT_TABLES:
            try:
                out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.OperationalError:
                out[t] = -1  # 표가 없음
        return out
    finally:
        conn.close()


def backup(label: str = "") -> Path:
    if not config.DB_PATH.exists():
        sys.exit(f"DB 파일이 없어요: {config.DB_PATH}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    safe = re.sub(r"[^0-9A-Za-z가-힣_-]", "", label)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"stockrule_{stamp}{'_' + safe if safe else ''}.db"

    src = sqlite3.connect(config.DB_PATH, timeout=30)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)  # 쓰는 중이어도 일관된 스냅샷
    finally:
        dst.close()
        src.close()

    # 검증: 무결성과 건수
    chk = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    try:
        ok = chk.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        chk.close()
    if ok != "ok":
        dest.unlink(missing_ok=True)
        sys.exit(f"백업 검증 실패(integrity_check={ok}). 백업 파일을 지웠어요.")

    # 종목 풀 JSON도 같은 이름으로 함께 보관
    if UNIVERSE_JSON.exists():
        shutil.copy2(UNIVERSE_JSON, dest.with_suffix(".universe.json"))

    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"백업 완료: {dest.relative_to(config.ROOT)} ({size_mb:.1f}MB)")
    print("  건수:", ", ".join(f"{k}={v}" for k, v in _counts(dest).items()))
    return dest


def list_backups() -> None:
    files = sorted(BACKUP_DIR.glob("stockrule_*.db"))
    if not files:
        print("백업이 없어요.")
        return
    for f in files:
        c = _counts(f)
        print(f"{f.name}  {f.stat().st_size / 1024 / 1024:.1f}MB  stocks={c['stocks']} prices={c['prices_daily']} financials={c['financials']}")


def prune(keep: int) -> None:
    files = sorted(BACKUP_DIR.glob("stockrule_*.db"))
    for f in files[:-keep] if keep > 0 else []:
        f.unlink()
        f.with_suffix(".universe.json").unlink(missing_ok=True)
        print(f"오래된 백업 삭제: {f.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SQLite DB 백업")
    ap.add_argument("--label", default="", help="파일명에 붙일 라벨 (예: universe)")
    ap.add_argument("--list", action="store_true", help="백업 목록 보기")
    ap.add_argument("--keep", type=int, default=0, help="백업 후 최근 N개만 남기기")
    a = ap.parse_args()

    if a.list:
        list_backups()
    else:
        backup(a.label)
        if a.keep:
            prune(a.keep)
