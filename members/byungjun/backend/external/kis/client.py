"""한투 Open API 저수준 클라이언트 — 조회 전용.

실전 계좌 키를 쓰므로 허용 목록에 없는 경로는 호출 전에 예외를 낸다.
주문·계좌 경로는 허용 목록에 넣지 않는다. 종목분석 7종(대차대조표 등, 2026-11-11 16:00 이후 차단)도 넣지 않는다.
키는 config에서만 읽고 어디에도 출력하지 않는다.
"""
import json
import time
from pathlib import Path

import config
from external.http import ExternalError, Throttle, request

# (경로, tr_id). 실전/모의 TR ID가 같은 것만 적었다(공식 예제 기준).
ALLOWED = {
    ("/oauth2/tokenP", None),
    ("/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100"),
    ("/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", "FHKST03010100"),
    ("/uapi/domestic-stock/v1/ksdinfo/dividend", "HHKDB669102C0"),
    ("/uapi/domestic-stock/v1/quotations/search-stock-info", "CTPF1002R"),
}
BASES = {
    "real": "https://openapi.koreainvestment.com:9443",
    "mock": "https://openapivts.koreainvestment.com:29443",
}
_throttle = Throttle(config.KIS_MIN_INTERVAL)
_TOKEN_FILE = config.ROOT / ".cache" / f"kis_token_{config.KIS_ENV}.json"


def _check(path: str, tr_id: str | None) -> None:
    if (path, tr_id) not in ALLOWED:
        raise PermissionError(f"허용되지 않은 한투 API 호출: {path} {tr_id}")


def _token() -> str:
    # 만료 전에는 캐시한 토큰을 재사용한다(호출마다 새로 발급하지 않음).
    if _TOKEN_FILE.exists():
        c = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
        if c["expires_at"] > time.time() + 60:
            return c["access_token"]
    if not (config.KIS_APP_KEY and config.KIS_APP_SECRET):
        raise ExternalError("KIS 키가 설정되지 않았습니다")
    _check("/oauth2/tokenP", None)
    d = request(BASES[config.KIS_ENV] + "/oauth2/tokenP", _throttle, body={
        "grant_type": "client_credentials",
        "appkey": config.KIS_APP_KEY,
        "appsecret": config.KIS_APP_SECRET,
    })
    _TOKEN_FILE.parent.mkdir(exist_ok=True)
    _TOKEN_FILE.write_text(json.dumps({
        "access_token": d["access_token"],
        "expires_at": time.time() + int(d.get("expires_in", 86400)),
    }), encoding="utf-8")
    return d["access_token"]


def get(path: str, tr_id: str, params: dict) -> dict:
    """허용된 조회 API 한 건을 부르고 원본 응답(dict)을 돌려준다. 정규화는 quotes.py가 한다."""
    _check(path, tr_id)
    res = request(BASES[config.KIS_ENV] + path, _throttle, params=params, headers={
        "authorization": "Bearer " + _token(),
        "appkey": config.KIS_APP_KEY,
        "appsecret": config.KIS_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    })
    if res.get("rt_cd") != "0":
        raise ExternalError(f"KIS 오류 {res.get('msg_cd')} {res.get('msg1')}")
    return res
