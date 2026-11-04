"""LLM 출력(조건 JSON) 검증.

LLM은 자연어를 조건으로 번역하거나 요청 종류를 분류만 한다. 판정은 코드가 한다.
검증을 통과하지 못한 출력은 호출한 쪽에서 재시도하거나 되묻기로 돌린다.

출력 형식:
{
  "intent": INTENTS 중 하나,
  "needs_clarification": bool,        # principle에서만 true 가능
  "question": str | null,             # 되묻기 질문
  "choices": [str, ...],              # 되묻기 선택지 (직접 입력은 UI가 따로 제공)
  "conditions": [
    {"indicator": CODE, "op": "<"|"<="|">"|">="|"==", "value": number,
     "period_months": int | null}    # PERIOD_RETURN일 때만 사용
  ],
  "unsupported_terms": [str, ...],    # 20개 밖이라 못 바꾼 용어 (예: "ROE")
  "message": str | null               # 사용자에게 보여 줄 안내문
}

intent:
  principle              원칙을 지표 조건으로 변환 (되묻기 포함)
  unsupported_indicator  20개 밖의 지표만 요청 -> 안내
  explain                용어·지표·결과 해석 설명 요청 (앱이 설명문을 보여 줌)
  manage                 원칙 수정·삭제·승인 등 앱 조작 (앱이 처리)
  simulate               점검·시뮬레이션 요청 (앱이 처리)
  off_topic              투자 원칙과 무관하거나 범위 밖 (추천, 보장, 알림 등)
"""
import json
from typing import Any

from .indicators import INDICATORS

OPS = ("<", "<=", ">", ">=", "==")
INTENTS = ("principle", "unsupported_indicator", "explain", "manage",
           "simulate", "off_topic")
MESSAGE_REQUIRED = ("unsupported_indicator", "off_topic")
PERIODS = (1, 3, 6, 12)  # UI 시뮬레이션 기간과 같게 둔다


def _str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(s, str) and s for s in v)


def validate(obj: Any) -> list:
    """오류 메시지 목록을 돌려준다. 빈 목록이면 유효."""
    errors = []
    if not isinstance(obj, dict):
        return ["최상위가 객체가 아님"]

    intent = obj.get("intent")
    if intent not in INTENTS:
        errors.append(f"intent는 {INTENTS} 중 하나여야 함: {intent!r}")

    nc = obj.get("needs_clarification")
    if not isinstance(nc, bool):
        errors.append("needs_clarification은 bool이어야 함")

    question = obj.get("question")
    if question is not None and not isinstance(question, str):
        errors.append("question은 문자열 또는 null")

    message = obj.get("message")
    if message is not None and not isinstance(message, str):
        errors.append("message는 문자열 또는 null")

    choices = obj.get("choices", [])
    if not _str_list(choices):
        errors.append("choices는 문자열 목록이어야 함")
    terms = obj.get("unsupported_terms", [])
    if not _str_list(terms):
        errors.append("unsupported_terms는 문자열 목록이어야 함")

    conds = obj.get("conditions")
    if not isinstance(conds, list):
        return errors + ["conditions는 목록이어야 함"]

    if nc is True:
        if intent != "principle":
            errors.append("되묻기는 principle에서만 가능함")
        if not question:
            errors.append("needs_clarification이면 question이 필요함")
        if not choices:
            errors.append("needs_clarification이면 choices가 필요함")
        if conds:
            errors.append("되묻기 중에는 conditions를 확정하지 않음")
    elif question or choices:
        errors.append("되묻기가 아니면 question/choices는 비워야 함")

    if intent in MESSAGE_REQUIRED and not message:
        errors.append(f"{intent}는 message가 필요함")
    if intent == "principle" and not nc and not conds:
        errors.append("principle이 확정이면 conditions가 필요함")
    if intent != "principle" and conds:
        errors.append(f"{intent}는 conditions가 비어 있어야 함")
    if intent in ("unsupported_indicator",) and not terms:
        errors.append("unsupported_indicator는 unsupported_terms가 필요함")
    if intent not in ("principle", "unsupported_indicator") and terms:
        errors.append(f"{intent}는 unsupported_terms를 쓰지 않음")

    seen = set()
    for i, c in enumerate(conds):
        p = f"conditions[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{p}: 객체가 아님")
            continue
        ind = INDICATORS.get(c.get("indicator"))
        if ind is None:
            errors.append(f"{p}: 지표 코드가 목록에 없음: {c.get('indicator')!r}")
            continue
        if c.get("op") not in OPS:
            errors.append(f"{p}: op는 {OPS} 중 하나여야 함")
        v = c.get("value")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            errors.append(f"{p}: value는 숫자여야 함")
        elif not (ind.lo <= v <= ind.hi):
            errors.append(f"{p}: {ind.code} 값 {v}이(가) 범위 {ind.lo}~{ind.hi}를 벗어남")
        pm = c.get("period_months")
        if ind.needs_period:
            if pm not in PERIODS:
                errors.append(f"{p}: {ind.code}는 period_months가 {PERIODS} 중 하나여야 함")
        elif pm is not None:
            errors.append(f"{p}: {ind.code}는 period_months를 쓰지 않음")
        key = (c.get("indicator"), c.get("op"), pm)
        if key in seen:
            errors.append(f"{p}: 같은 지표·연산자 조건이 중복됨")
        seen.add(key)
    return errors


def parse_and_validate(text: str):
    """모델이 낸 문자열을 JSON으로 읽고 검증한다. (객체 또는 None, 오류 목록)"""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        return None, [f"JSON 문법 오류: {e}"]
    return obj, validate(obj)
