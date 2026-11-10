"""서버 설정. 값은 모두 backend/.env 또는 환경변수에서 읽는다.

키는 이 파일에서도 출력하지 않는다.
"""
import os
from pathlib import Path

ROOT = Path(__file__).parent


def _load_env_file() -> None:
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_env_file()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


# --- 키 (값이 비어 있어도 서버는 뜬다. fixture 모드에서는 필요 없음) ---
KIS_APP_KEY = env("KIS_APP_KEY")
KIS_APP_SECRET = env("KIS_APP_SECRET")
DART_API_KEY = env("DART_API_KEY")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")

# --- 모드 ---
# KIS_ENV: real 또는 mock (예전 값 prod/vps도 같은 뜻으로 받는다)
KIS_ENV = {"prod": "real", "vps": "mock"}.get(env("KIS_ENV", "real"), env("KIS_ENV", "real"))
# EXTERNAL_MODE: live(실제 호출) 또는 fixture(external/fixtures 샘플 사용)
EXTERNAL_MODE = env("EXTERNAL_MODE", "live")
# LLM_PROVIDER: anthropic 또는 local (원칙 변환 FR-01에 쓴다. 종합 리포트는 항상 Anthropic)
LLM_PROVIDER = env("LLM_PROVIDER", "anthropic")
LLM_MODEL = env("LLM_MODEL", "claude-haiku-5-5")
LOCAL_LLM_URL = env("LOCAL_LLM_URL", "http://localhost:11434")  # Ollama 기본 주소 (미확인)
LOCAL_LLM_MODEL = env("LOCAL_LLM_MODEL", "qwen3-8b-stockrule")

# --- 호출 제어 (한도 수치는 공식 문서로 확인 필요 — docs/external-api-notes.md) ---
KIS_MIN_INTERVAL = float(env("KIS_MIN_INTERVAL", "0.6"))  # 초. 실측으로 0.12초는 제한에 걸렸다
DART_MIN_INTERVAL = float(env("DART_MIN_INTERVAL", "0.2"))
HTTP_TIMEOUT = float(env("HTTP_TIMEOUT", "20"))
# 요청 시점에 한투·DART를 먼저 부른다(1). 끄면(0) DB 저장분만 읽는다. TTL 안에는 같은 종목을 다시 받지 않는다.
LIVE_FETCH = env("LIVE_FETCH", "1") == "1"
LIVE_TTL_SEC = float(env("LIVE_TTL_SEC", "300"))
# 서버가 켜져 있으면 장 마감(평일 15:40) 뒤 DB 일봉·현재가를 자동으로 새로 받는다(1). 끄기(0)
PRICE_REFRESH = env("PRICE_REFRESH", "1") == "1"
MAX_RETRIES = 2  # 한도 초과(429)나 5xx만

# --- 앱 설정 ---
DB_PATH = ROOT / env("DB_FILE", "data/stockrule.db")
FIXTURE_DIR = ROOT / "external" / "fixtures"
FIXED_USER_ID = "jangyechan"  # 회원가입 없음, 이 계정으로 고정

# --- DART 지표 계산 기준 (여기 한 곳에서 바꾼다) ---
DART_CONSOLIDATED_FIRST = True  # 연결재무제표를 우선 쓰고 없으면 별도로 폴백
