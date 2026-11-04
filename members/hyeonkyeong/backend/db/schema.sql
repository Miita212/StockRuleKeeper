-- 사용자별 원칙(버전 관리), 종목, 수집 데이터. SQLite.

CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY
);

-- 원칙 한 개 = principles 한 행, 수정할 때마다 principle_versions에 새 버전을 쌓는다.
CREATE TABLE IF NOT EXISTS principles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL REFERENCES users(user_id),
  name TEXT NOT NULL,
  current_version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS principle_versions (
  principle_id INTEGER NOT NULL REFERENCES principles(id),
  version INTEGER NOT NULL,
  indicators_json TEXT NOT NULL,   -- [{id, operator, value, unit, locked}] 20개
  reason TEXT,                     -- "이렇게 만들었어요" 설명
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (principle_id, version)
);

-- 반도체 종목 풀 (batch/build_universe.py 결과 + 수동 보강)
CREATE TABLE IF NOT EXISTS stocks (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  market TEXT,
  industry_name TEXT,
  source TEXT NOT NULL DEFAULT 'auto'   -- auto(한투 분류) 또는 manual(수동 보강)
);

CREATE TABLE IF NOT EXISTS corp_codes (
  stock_code TEXT PRIMARY KEY,
  corp_code TEXT NOT NULL,
  corp_name TEXT
);

CREATE TABLE IF NOT EXISTS prices_daily (
  code TEXT NOT NULL,
  date TEXT NOT NULL,
  close REAL, volume REAL, value REAL,
  PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS dividends (
  code TEXT NOT NULL,
  record_date TEXT NOT NULL,
  pay_date TEXT,
  amount_per_share REAL,
  kind TEXT,
  PRIMARY KEY (code, record_date, kind)
);

CREATE TABLE IF NOT EXISTS snapshots (       -- 현재가 시세 스냅샷(수집 시점 값)
  code TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  json TEXT NOT NULL,
  PRIMARY KEY (code, fetched_at)
);

CREATE TABLE IF NOT EXISTS financials (      -- DART 재무제표 원본 행(정규화 후)
  code TEXT NOT NULL,
  year INTEGER NOT NULL,
  reprt_code TEXT NOT NULL,
  basis TEXT NOT NULL,                       -- CFS(연결) 또는 OFS(별도)
  rows_json TEXT NOT NULL,
  PRIMARY KEY (code, year, reprt_code)
);

CREATE TABLE IF NOT EXISTS shares (          -- 가상 주식앱 "공유하기"
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  code TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
