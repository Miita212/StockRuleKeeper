"""원칙 변환(FR-01): 초보자의 말 한 문장 -> 20개 지표 중 해당 지표의 연산자·값.

모델은 지표 id와 값만 정하고, 이름·단위·판정은 코드가 붙인다. 모델 출력은 services/principles.py 가 검증한다.
LLM_PROVIDER=local 이면 파인튜닝한 Qwen3-8B(Ollama), anthropic 이면 Haiku few-shot 로 같은 프롬프트를 쓴다.
"""
import json

from indicators.master import MASTER, OPERATOR_WORDS, RANGES
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
        lines.append(f"- id {m['id']}: {m['name']} (단위 {m['unit']}, 보통 '{word}' 방향, 값 범위 {lo}~{hi})")
    return "\n".join(lines)


def system_prompt() -> str:
    return f"""당신은 투자 초보자의 말을 정량 지표 조건으로 바꾸는 변환기입니다. 대상은 반도체 업종 종목입니다.
아래 20개 지표(id)만 사용할 수 있습니다.
{indicator_table()}

[규칙]
1. 모든 입력은 위 20개 정량 지표로만 변환하세요. 투자와 무관한 말이면 needs_clarification=true 로 하고 clarify.message 에 "투자 원칙과 관련된 말씀을 해 주세요"라고 안내하세요.
2. 방향을 지키세요. 예: "빚 적은" -> 부채비율 이하(<=), "배당 많이" -> 배당수익률 이상(>=). 지표의 보통 방향과 반대 연산자를 쓰지 마세요.
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
    """모델 원본 출력(dict)을 돌려준다. 검증은 services.principles.normalize 가 한다."""
    return complete_json(system_prompt(), user_prompt(text, base, locked_ids or [], history or []),
                         sample="llm_principle.json")
