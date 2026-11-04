"""LLM 호출 어댑터. 상위 모듈은 complete_json(...)만 쓴다(Anthropic·로컬 응답 형식을 모른다).

- provider="anthropic": Anthropic Messages API (LLM_MODEL)
- provider="local":     로컬 Ollama /api/chat (원칙 변환 FR-01용 파인튜닝 모델)
- EXTERNAL_MODE=fixture 이면 sample 이름의 샘플 JSON을 그대로 돌려준다(llm_principle / llm_report).
종합 리포트는 항상 provider="anthropic"으로 부른다.
"""
import json
import re

import config
from external.fixtures import load
from external.http import ExternalError, Throttle, request

_throttle = Throttle(0.0)
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _anthropic(system: str, user: str, max_tokens: int) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise ExternalError("ANTHROPIC 키가 설정되지 않았습니다")
    res = request(ANTHROPIC_URL, _throttle, headers={
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
    }, body={
        "model": config.LLM_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    })
    return "".join(b.get("text", "") for b in res.get("content", []))


def _local(system: str, user: str) -> str:
    res = request(config.LOCAL_LLM_URL + "/api/chat", _throttle, body={
        "model": config.LOCAL_LLM_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "format": "json",
    })
    return res["message"]["content"]


def _parse_json(text: str) -> dict:
    # 모델이 ```json 으로 감싸거나 앞뒤에 글을 붙여도 첫 JSON 객체만 꺼낸다.
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ExternalError("LLM 응답에서 JSON을 찾지 못했습니다")
    return json.loads(m.group(0))


def complete_json(system: str, user: str, sample: str, provider: str | None = None,
                  max_tokens: int = 2048) -> dict:
    """sample: fixture 모드에서 돌려줄 샘플 이름(예: "llm_principle.json")."""
    if config.EXTERNAL_MODE == "fixture":
        return load(sample)
    provider = provider or config.LLM_PROVIDER
    text = _anthropic(system, user, max_tokens) if provider == "anthropic" else _local(system, user)
    return _parse_json(text)
