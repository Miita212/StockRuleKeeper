"""외부 API 공통 호출: 호출 간격 제어, 타임아웃, 재시도(최대 2회, 한도 초과·5xx만).

오류 메시지에 URL의 쿼리나 헤더(키)를 넣지 않는다.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

import config


class ExternalError(Exception):
    pass


class Throttle:
    """같은 서비스로 가는 호출 사이에 최소 간격을 둔다."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        gap = time.monotonic() - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last = time.monotonic()


def request(url: str, throttle: Throttle, headers: dict | None = None, params: dict | None = None,
            body: dict | None = None, raw: bool = False):
    """GET(params) 또는 POST(body)를 보내고 JSON(또는 raw=True면 bytes)을 돌려준다."""
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    hdrs = dict(headers or {})
    if data is not None:
        hdrs.setdefault("content-type", "application/json")
    for attempt in range(config.MAX_RETRIES + 1):
        throttle.wait()
        try:
            req = urllib.request.Request(full, data, hdrs)
            with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as r:
                content = r.read()
            return content if raw else json.loads(content)
        except urllib.error.HTTPError as e:
            retryable = e.code == 429 or e.code >= 500
            if not retryable or attempt == config.MAX_RETRIES:
                raise ExternalError(f"HTTP {e.code} ({urllib.parse.urlparse(url).path})") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == config.MAX_RETRIES:
                raise ExternalError(f"연결 실패 ({urllib.parse.urlparse(url).path})") from None
        time.sleep(1.5 * (attempt + 1))
