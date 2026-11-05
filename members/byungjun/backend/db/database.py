import sqlite3
from pathlib import Path

import config


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)  # 수집 배치가 쓰는 중이어도 잠시 기다린다
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """표를 만들고 고정 사용자(jangyechan)를 넣는다."""
    with connect() as conn:
        try:
            conn.execute("PRAGMA journal_mode=WAL")  # 읽기와 쓰기가 서로 막지 않게 한다
        except sqlite3.OperationalError:
            pass  # 다른 프로세스가 쓰는 중이면 다음 기동 때 바꾼다
        conn.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (config.FIXED_USER_ID,))
