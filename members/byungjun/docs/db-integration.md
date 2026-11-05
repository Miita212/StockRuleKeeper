# DB 연동 (byungjun 백엔드 기준)

원본: `members/yappang/docs/db-integration.md`(2026-11-05). 경로는 모두 `members/byungjun/backend/` 기준이다.
원본에서 byungjun 백엔드의 현재 동작에 맞게 고친 곳은 아래 "(byungjun 수정)"으로 표시했다. 자세한 변경은 `members/byungjun/수정내역.md`.

DB는 SQLite 단일 파일(`data/stockrule.db`)이다. 경로는 `config.DB_PATH`로 정해지고 환경변수 `DB_FILE`로 바꿀 수 있다. ORM 없이 `sqlite3`로 직접 SQL을 쓴다.

## 1. 연결과 스키마 (공통 기반)

| 파일 | 역할 |
|---|---|
| `db/database.py` | `connect()`는 연결을 만든다(타임아웃 30초, `row_factory=Row`). `init_db()`는 WAL 모드를 켜고, `schema.sql`을 실행하고, 고정 사용자(`jangyechan`)를 넣는다. |
| `db/schema.sql` | 표 10개를 정의한다: users, principles, principle_versions, stocks, corp_codes, prices_daily, dividends, snapshots, financials, shares |
| `main.py` | 서버 기동 시(`lifespan`) `init_db()`를 호출하고, `stocks` 표가 비어 있으면 `seed_stocks()`로 종목 풀 파일(`data/semiconductor_universe.json`) 113개를 채운다. (byungjun 수정) |
| `config.py` | `DB_PATH`(`data/stockrule.db`)와 `FIXED_USER_ID`를 정의한다. |

## 2. API 계층 (`api/`)

요청마다 `with connect()`로 연결을 열고 서비스에 넘긴다.

| 파일 | DB 처리 |
|---|---|
| `api/principles.py` | 원칙 CRUD. 이름 수정은 `UPDATE principles`를 직접 실행한다. |
| `api/stocks.py` | `/virtual/stocks`는 `stocks`와 `prices_daily`를 읽는다. `/shares`는 `shares`에 INSERT하고 조회한다. |
| `api/simulation.py` | 연결만 열고 서비스에 위임한다. |

## 3. 서비스 계층 (`services/`)

실제 쿼리가 있는 곳이다.

| 파일 | 읽기/쓰기 표 |
|---|---|
| `services/principles.py` | `principles`, `principle_versions`에 생성·버전 추가·수정·삭제·조회. 쓰기가 가장 많다. |
| `services/stocks.py` | 최신 원칙 조회, `prices_daily`로 등락률 계산, `stocks` 검색. 종목 계산 전에 `services/live.py`로 한투 데이터를 먼저 받는다. (byungjun 수정) |
| `services/live.py` | (byungjun 추가) 한투 현재가 스냅샷·일봉·배당을 API로 먼저 받아 `snapshots`, `prices_daily`, `dividends`에 저장한다. 종목별 `LIVE_TTL_SEC`(기본 300초) 안에는 다시 받지 않고, 실패하면 DB 값을 쓴다. DART는 부르지 않는다. |
| `services/simulation.py` | `stocks` 전체 목록 조회 |

## 4. 지표 계산 (`indicators/compute.py`)

읽기 전용이다. (byungjun 수정: 이 파일은 DB만 읽고, 최신 한투 데이터는 호출하는 쪽이 `services/live.py`로 먼저 받아 둔다.) `prices_daily`, `dividends`, `snapshots`, `financials`를 읽어 지표를 계산한다.

## 5. 배치 (`batch/`)

외부 API 데이터를 DB에 채운다. (byungjun 수정) 한투 데이터(현재가·일봉·배당)는 요청 때 API로 먼저 받아 DB에 저장하고, DART 재무제표는 이 배치로 채운 DB 값만 읽는다. 시뮬레이션도 DB 값만 읽는다.

| 파일 | 쓰는 표 |
|---|---|
| `batch/build_universe.py` | `stocks` (INSERT OR REPLACE) |
| `batch/collect_data.py` | `prices_daily`, `snapshots`, `dividends`, `financials`, `corp_codes` (모두 INSERT OR REPLACE). 이어받기를 위해 기존 건수를 먼저 조회한다. |

실행 순서: `build_universe.py`(종목 풀) → `collect_data.py`(시세·배당·재무). 둘 다 `EXTERNAL_MODE=live`와 키가 필요하다.

## 6. 백업과 기타

> (byungjun 수정) 아래 `db/backup.py`와 `scripts/test_stocks.py`는 yappang 쪽 백엔드에 있는 파일이다. 이 폴더(byungjun/backend)에는 아직 없다.

- `db/backup.py`: SQLite 백업 API로 스냅샷을 만든다. 서버나 배치가 쓰는 중에도 안전하다.
  - `python db/backup.py --label universe`: 백업. 결과는 `db/backups/`에 저장되고 gitignore 대상이다.
  - `python db/backup.py --list`: 백업 목록과 건수
  - `python db/backup.py --keep 10`: 백업 후 최근 10개만 남김
  - 복원: 백엔드와 배치를 끈 뒤 `rm -f data/stockrule.db-wal data/stockrule.db-shm`, `cp db/backups/<파일>.db data/stockrule.db`
- `scripts/test_stocks.py`: 테스트용으로 DB에 접근한다.

## 7. 특징과 주의

- **연결 생성은 `db/database.py`의 `connect()` 한 곳**에 모여 있지만, SQL은 `api/`, `services/`, `indicators/`, `batch/`에 흩어져 있다.
- **쓰기 주체는 세 곳**이다: 서비스(원칙·공유), 배치(시장 데이터), `init_db`(스키마·사용자).
- 배치가 쓰는 동안 서버가 읽을 수 있도록 WAL 모드와 30초 타임아웃을 둔다. `.db` 파일만 `cp`로 복사하면 WAL의 최근 내용이 빠질 수 있으니 백업은 `db/backup.py`를 쓴다.
- `data/*.db`, `data/*.db-wal`, `data/*.db-shm`, `db/backups/`는 `.gitignore` 대상이다. 커밋하지 않는다.
