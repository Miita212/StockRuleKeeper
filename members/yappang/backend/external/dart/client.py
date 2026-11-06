"""OpenDART 저수준 클라이언트. 키는 config에서만 읽고 출력하지 않는다."""
import config
from external.http import ExternalError, Throttle, request

BASE = "https://opendart.fss.or.kr/api"
_throttle = Throttle(config.DART_MIN_INTERVAL)


def _auth(params: dict) -> dict:
    if not config.DART_API_KEY:
        raise ExternalError("DART 키가 설정되지 않았습니다")
    return {**params, "crtfc_key": config.DART_API_KEY}


def get_json(endpoint: str, params: dict) -> dict:
    res = request(f"{BASE}/{endpoint}", _throttle, params=_auth(params))
    return res


def get_bytes(endpoint: str, params: dict) -> bytes:
    return request(f"{BASE}/{endpoint}", _throttle, params=_auth(params), raw=True)
