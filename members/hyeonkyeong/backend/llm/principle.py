"""원칙 변환(FR-01): 초보자의 말 한 문장 -> 20개 지표 중 해당 지표의 연산자·값.

모델은 지표 id와 값만 정하고, 이름·단위·판정은 코드가 붙인다. 모델 출력은 services/principles.py 가 검증한다.
LLM_PROVIDER=local 이면 파인튜닝한 Qwen3-8B(Ollama), anthropic 이면 Haiku few-shot 로 같은 프롬프트를 쓴다.
"""
import json

import config
from indicators.master import BOTH_WAYS, MASTER, OPERATOR_WORDS, RANGES, criterion_text
from llm.provider import complete_json

SCHEMA = """{
  "needs_clarification": true 또는 false,
  "clarify": null 또는 {"message": "되묻는 말(해요체)", "options": [{"label": "선택지 이름", "indicator_id": 지표 id, "operator": "<=|>=|<|>", "value": 숫자}]},
  "name": "원칙 이름(15자 이내)",
  "anchors": [사용자 말에서 나온 지표 id],
  "indicators": [{"id": 지표 id, "operator": "<=|>=|<|>", "value": 숫자, "source": "user|inferred"}],
  "explain_bubble": "왜 이렇게 정했는지 1~2문장(해요체)",
  "explain_card": "원칙 전체를 쉬운 말로 설명 2~3문장(해요체)"
}"""

EXAMPLES = """[예시 1] 입력: "빚 많은 회사는 피하고 싶어"
{"needs_clarification": false, "clarify": null, "name": "빚 적은 회사 원칙", "anchors": [1],
 "indicators": [{"id": 1, "operator": "<=", "value": 100, "source": "user"}],
 "explain_bubble": "빚이 많은 회사는 피하고 싶다고 하셔서 부채비율을 100% 이하로 정했어요.",
 "explain_card": "갚아야 할 빚이 내 돈(자본)보다 많지 않은 회사만 고르는 원칙이에요."}

[예시 2] 입력: "너무 비싼 주식은 안 살래"  (기준이 불명확하므로 추측하지 말고 되묻는다)
{"needs_clarification": true,
 "clarify": {"message": "'비싸다'는 이익이나 순자산에 비해 주가가 높다는 뜻일 수 있어요. 어떤 기준으로 볼까요?",
   "options": [{"label": "PER 10배 이하 (엄격)", "indicator_id": 10, "operator": "<=", "value": 10},
               {"label": "PER 15배 이하 (보통)", "indicator_id": 10, "operator": "<=", "value": 15},
               {"label": "PER 20배 이하 (느슨)", "indicator_id": 10, "operator": "<=", "value": 20}]},
 "name": "", "anchors": [], "indicators": [], "explain_bubble": "", "explain_card": ""}"""


def indicator_table() -> str:
    lines = []
    for m in MASTER.values():
        lo, hi = RANGES[m["id"]]
        word = m["word"] or OPERATOR_WORDS[m["operator"]]
        both = ", 반대 방향도 가능" if m["id"] in BOTH_WAYS else ""
        lines.append(f"- id {m['id']}: {m['name']} (단위 {m['unit']}, 보통 '{word}' 방향{both}, 값 범위 {lo}~{hi})")
    return "\n".join(lines)


def system_prompt() -> str:
    return f"""당신은 투자 초보자의 말을 정량 지표 조건으로 바꾸는 변환기입니다. 대상은 반도체 업종 종목입니다.
아래 20개 지표(id)만 사용할 수 있습니다.
{indicator_table()}

[규칙]
1. 모든 입력은 위 20개 정량 지표로만 변환하세요. 투자와 무관한 말이면 needs_clarification=true 로 하고 clarify.message 에 "투자 원칙과 관련된 말씀을 해 주세요"라고 안내하세요.
2. 방향을 지키세요. 예: "빚 적은" -> 부채비율 이하(<=), "배당 많이" -> 배당수익률 이상(>=). "반대 방향도 가능"이라고 적힌 지표가 아니면 보통 방향과 반대 연산자를 쓰지 마세요.
3. 임계값이 불명확하면 추측하지 말고 needs_clarification=true 로 하고, clarify.options 에 엄격·보통·느슨 3개를 주세요.
4. 사용자 말에서 나온 지표만 indicators 에 넣으세요. 나머지 지표의 기본값은 코드가 채웁니다.
5. 사용자가 잠근 지표(locked)는 바꾸지 마세요. 현재 원칙이 주어지면 사용자 말에 해당하는 지표만 고쳐서 돌려주세요.
6. 말투는 "~해요"체. 종목 추천, 수익 예측·보장 표현을 쓰지 마세요.
7. 아래 JSON 형식 하나만 출력하고 다른 글은 쓰지 마세요.
{SCHEMA}

{EXAMPLES}"""


def user_prompt(text: str, base: dict | None, locked_ids: list[int], history: list[str]) -> str:
    payload = {"입력": text}
    if history:
        payload["이전 대화"] = history
    if base:
        payload["현재 원칙"] = [{"id": i, "operator": v["operator"], "value": v["value"]} for i, v in sorted(base.items())]
    if locked_ids:
        payload["잠근 지표(변경 금지)"] = sorted(locked_ids)
    return json.dumps(payload, ensure_ascii=False)


def ask_model(text: str, base: dict | None = None, locked_ids: list[int] | None = None,
              history: list[str] | None = None) -> dict:
    """모델 출력을 위 SCHEMA 모양(dict)으로 돌려준다. 검증은 services.principles.normalize 가 한다."""
    locked_ids, history = locked_ids or [], history or []
    if config.LLM_PROVIDER == "local":
        return ask_local(text, base, locked_ids, history)
    return complete_json(system_prompt(), user_prompt(text, base, locked_ids, history),
                         sample="llm_principle.json")


# ---------------------------------------------------------------------------
# 로컬 파인튜닝 모델(Qwen3-8B). 팀 학습 데이터(byungjun/finetune_merged)와 글자 그대로 같은 형식으로 부른다.
# 모델은 학습 형식으로 답하므로 from_trained 가 위 SCHEMA 모양으로 바꾼다.
# ---------------------------------------------------------------------------
LOCAL_SYSTEM = ('너는 투자 원칙 점검 앱의 도우미야. 사용자의 말을 지표 20개 기준 JSON으로 바꿔. '
                'JSON만 출력하고, 종목 추천이나 수익 예측은 하지 않아.')  # 학습 데이터 system 문구 그대로

# 학습 데이터는 시가총액(14)을 억원으로 쓴다(1조원 = 10000). 우리 원칙은 조원.
MODEL_SCALE = {14: 10000}
MODEL_UNIT = {14: "억원"}

# 되묻기 대화(여러 턴). 사용자는 jangyechan 하나뿐이라 한 개만 기억한다.
_dialog: dict = {"users": [], "messages": []}


def _to_model(i: int, v: float):
    v = v * MODEL_SCALE.get(i, 1)
    return int(v) if float(v).is_integer() else v


def _from_model(i: int, v):
    return None if v is None else v / MODEL_SCALE.get(i, 1)


def current_rule_text(base: dict, locked_ids: list[int]) -> str:
    """원칙 수정(S4) 입력의 "현재 원칙: {...}" 부분."""
    items = []
    for i, x in sorted(base.items()):
        item = {"id": i, "operator": x["operator"], "value": _to_model(i, x["value"]),
                "unit": MODEL_UNIT.get(i, MASTER[i]["unit"]), "source": x.get("source", "default")}
        if i in locked_ids:
            item["locked"] = True
        if x.get("period_months"):
            item["period_months"] = x["period_months"]
        items.append(item)
    return "현재 원칙: " + json.dumps({"indicators": items}, ensure_ascii=False)


def local_messages(text: str, base: dict | None, locked_ids: list[int], history: list[str]) -> list[dict]:
    if history:  # 되묻기에 대한 답: 앞선 대화(모델의 되묻기 포함)를 이어 붙인다(S3 형식)
        # 첫 문장이 같으면 같은 대화로 본다(화면에 따라 history에 첫 문장만 보내는 경우가 있다)
        if _dialog["users"] and _dialog["users"][0] == history[0]:
            msgs = list(_dialog["messages"])
        else:  # 서버가 다시 켜져 대화를 잃었으면 사용자 말만 이어 붙인다
            msgs = [{"role": "user", "content": h} for h in history]
        return msgs + [{"role": "user", "content": text}]
    if base:  # 원칙 수정(S4 형식)
        return [{"role": "user", "content": current_rule_text(base, locked_ids) + "\n요청: " + text}]
    return [{"role": "user", "content": text}]


def ask_local(text: str, base: dict | None, locked_ids: list[int], history: list[str]) -> dict:
    msgs = local_messages(text, base, locked_ids, history)
    raw = complete_json(LOCAL_SYSTEM, msgs[-1]["content"], sample="llm_principle.json", messages=msgs)
    if raw.get("needs_clarification"):
        _dialog.update(users=history + [text],
                       messages=msgs + [{"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)}])
    else:
        _dialog.update(users=[], messages=[])
    return from_trained(raw, base)


def summary_texts(settings: list[dict]) -> dict:
    """원칙 이름·설명 카드를 코드가 만든다(학습 형식에 없고, 수정 때 모델 설명은 바뀐 부분만 말하므로)."""
    if not settings:
        return {"name": "", "explain_card": ""}
    names = [MASTER[s["id"]]["name"] for s in settings]
    name = f"{names[0]} 원칙" if len(names) == 1 else f"{names[0]} 외 {len(names) - 1}개 원칙"
    texts = []
    for s in settings:
        try:
            texts.append(f"{MASTER[s['id']]['name']} {criterion_text(s['id'], s['operator'], float(s['value']))}")
        except (TypeError, ValueError):
            pass
    card = f"{', '.join(texts)}인 반도체 종목만 고르는 원칙이에요. 나머지 지표는 기본값이에요." if texts else ""
    return {"name": name, "explain_card": card}


def from_trained(raw: dict, base: dict | None = None) -> dict:
    """학습 형식 출력 -> SCHEMA 모양. 값 검증은 normalize 가 한다."""
    base = base or {}

    def op_of(i):
        return (base.get(i) or MASTER.get(i, {})).get("operator")

    if raw.get("refusal"):  # S5 거절: 안내만 보여 준다
        return {"needs_clarification": True, "clarify": {"message": raw.get("message", ""), "options": []}}

    if raw.get("needs_clarification"):  # S3 되묻기 3종
        reason = raw.get("reason")
        if reason == "VALUE_MISSING":
            i = raw.get("indicator_id")
            options = [{"label": o.get("label", ""), "indicator_id": i, "operator": op_of(i),
                        "value": _from_model(i, o.get("value"))} for o in raw.get("options") or []]
        elif reason == "PERIOD_MISSING":
            options = [{"label": o.get("label", "")} for o in raw.get("options") or []]
        else:  # AMBIGUOUS_INDICATOR: 지표 또는 영역 후보. 고르면 그 이름을 다시 보낸다
            # 학습 데이터에 label / name / area 세 가지 이름이 섞여 있다
            options = [{"label": c.get("label") or c.get("name") or c.get("area")
                        or MASTER.get(c.get("id"), {}).get("name", "")} for c in raw.get("candidates") or []]
        return {"needs_clarification": True, "clarify": {"message": raw.get("message", ""), "options": options}}

    if "changes" in raw:  # S4 수정: 바뀐 지표만 온다(연산자는 그대로)
        settings = [{"id": c.get("id"), "operator": op_of(c.get("id")),
                     "value": _from_model(c.get("id"), c.get("after")), "source": "user"}
                    for c in raw.get("changes") or []]
        # 잠겨서 못 바꾼 지표는 normalize 가 "잠겨 있어요" 안내를 하도록 그대로 넘긴다
        settings += [{"id": i, "operator": op_of(i), "value": (base.get(i) or MASTER[i])["value"], "source": "user"}
                     for i in raw.get("skipped_locked") or [] if i in MASTER]
        changed = [s for s in settings if s["id"] not in (raw.get("skipped_locked") or [])]
        return {"needs_clarification": False, "clarify": None, "anchors": [s["id"] for s in changed],
                "indicators": settings, "explain_bubble": "", **summary_texts(changed)}

    # 확정(SEED·S3 마지막): 20개 세트. 기본값(source=default)은 코드가 채우므로 사용자가 정한 것만 쓴다
    settings = []
    for x in raw.get("indicators") or []:
        if x.get("source") not in ("user", "inferred"):
            continue
        s = {"id": x.get("id"), "operator": x.get("operator"), "value": _from_model(x.get("id"), x.get("value")),
             "source": x["source"]}
        if x.get("period_months"):
            s["period_months"] = x["period_months"]
        settings.append(s)
    return {"needs_clarification": False, "clarify": None, "anchors": raw.get("anchors") or [s["id"] for s in settings],
            "indicators": settings, "explain_bubble": raw.get("explain_bubble", ""), **summary_texts(settings)}
