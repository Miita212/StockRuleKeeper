"""종합 리포트(13번 화면): 코드가 계산한 시뮬레이션 결과 -> Haiku가 문장만 쓴다. 정본 설계: project_details/07.

안전장치(코드): JSON 스키마 검사, 입력에 없는 숫자 검사, 금지어 검사 -> 어긋나면 재요청(최대 2회) -> 그래도 안 되면 템플릿.
종합 리포트는 LLM_PROVIDER와 상관없이 항상 Anthropic(Haiku)을 쓴다.
"""
import json
import re

from llm.provider import complete_json

SYSTEM = """당신은 초보 투자자를 돕는 "투자 원칙 점검 리포트" 작성자입니다.
사용자는 자신의 투자 원칙 수치를 직접 바꿔 보고, 바꾸기 전과 후를
과거 데이터로 비교해 보았습니다. 아래 입력 JSON은 이미 계산이 끝난 결과입니다.

[규칙]
1. 입력에 있는 숫자만 쓰세요. 새로 계산하거나 추정하거나 반올림하지 마세요.
   (예: 평균 수익률 차이는 입력 값을 그대로 인용하고, 직접 빼지 마세요.)
2. "어느 쪽이 더 낫다/좋다"고 결론 내리지 마세요. 수익, 변동성, 종목 수를
   함께 보여 주고, 장단점을 나란히 설명하세요.
3. 입력에 없는 원인(뉴스, 실적, 시장 상황 등)을 설명하지 마세요.
   원인이 궁금해 보이는 대목은 "이 데이터로는 이유를 알 수 없어요"라고 쓰세요.
4. 종목을 사라/팔라고 권하거나 특정 종목을 추천하지 마세요.
   종목 이름은 입력의 examples에 있는 것만, 사실 설명용으로 쓰세요.
5. 과거 결과가 미래를 보장하지 않는다는 점과, 이번 결과가 1개 구간·
   적은 종목 수에 기반한다는 한계를 반드시 알려 주세요(입력 data_notes와
   passed_count를 근거로).
6. 잠근 지표(locked_indicators)가 있으면 바뀌지 않았다는 점만 한 줄로 언급하세요.
7. 말투는 "~해요" 체, 주식 용어는 쉬운 말로 풀어 쓰고 처음 나올 때만
   괄호로 용어를 붙이세요. (예: 빚 비율(부채비율))
8. 반드시 아래 JSON 스키마만 출력하세요. 다른 글은 쓰지 마세요.

{"headline": "한 줄 요약 (40자 이내, 결론 단정 금지)",
 "what_changed": "무엇을 어떻게 바꿨는지 1~2문장",
 "comparison": [
  {"label": "조건에 맞는 종목 수", "before": "18개", "after": "11개", "note": "쉬운 한 줄 해석"},
  {"label": "평균 수익률", "before": "...", "after": "...", "note": "..."},
  {"label": "오른 종목 비율", "before": "...", "after": "...", "note": "..."},
  {"label": "기간 중 평균 최대 하락", "before": "...", "after": "...", "note": "..."}],
 "stock_changes": "빠지거나 추가된 종목 설명 2~3문장",
 "cautions": ["한계/주의 2~3개"],
 "think_about": ["사용자가 스스로 판단해 볼 질문 2~3개"]}"""

FORBIDDEN = ["추천", "사세요", "사라", "팔라", "더 좋", "더 낫", "유리해요", "유리합니다", "매수하", "매도하"]
LABELS = ["조건에 맞는 종목 수", "평균 수익률", "오른 종목 비율", "기간 중 평균 최대 하락"]
NUM = re.compile(r"\d+(?:\.\d+)?")


def _norm(x: str) -> str:
    return str(float(x)).rstrip("0").rstrip(".") if "." in x else str(int(x))


def _numbers(text: str) -> set[str]:
    return {_norm(n) for n in NUM.findall(text)}


def check(report: dict, allowed_json: str) -> list[str]:
    """스키마·숫자·금지어를 검사해 문제 목록을 돌려준다(빈 목록이면 통과)."""
    problems = []
    if not isinstance(report.get("headline"), str) or not isinstance(report.get("what_changed"), str):
        problems.append("headline/what_changed 형식")
    comp = report.get("comparison")
    if not (isinstance(comp, list) and [c.get("label") for c in comp if isinstance(c, dict)] == LABELS):
        problems.append("comparison 형식")
    if not isinstance(report.get("stock_changes"), str):
        problems.append("stock_changes 형식")
    for key in ("cautions", "think_about"):
        if not (isinstance(report.get(key), list) and report[key] and all(isinstance(x, str) for x in report[key])):
            problems.append(f"{key} 형식")
    text = json.dumps(report, ensure_ascii=False)
    extra = _numbers(text) - _numbers(allowed_json)
    if extra:
        problems.append(f"입력에 없는 숫자: {sorted(extra)}")
    hit = [w for w in FORBIDDEN if w in text]
    if hit:
        problems.append(f"금지 표현: {hit}")
    return problems


def _pct(v, plus=True):
    return "-" if v is None else f"{'+' if plus and v > 0 else ''}{v:g}%"


def template(sim: dict) -> dict:
    """LLM을 못 쓰거나 검사에 실패했을 때의 고정 문장 리포트(숫자는 입력 그대로)."""
    b, a = sim["before"], sim["after"]
    changes = ", ".join(f"{c['indicator']} {c['before']}→{c['after']}" for c in sim["changes"]) or "바꾼 기준이 없어요"
    dropped, added = sim["dropped_stocks"], sim["added_stocks"]
    parts = []
    if dropped["count"]:
        ex = ", ".join(f"{e['name']}({_pct(e['return_pct'])})" for e in dropped["examples"])
        parts.append(f"기준을 바꾸면서 {dropped['count']}개 종목이 빠졌어요. 예: {ex}.")
    if added["count"]:
        parts.append(f"{added['count']}개 종목이 새로 포함됐어요.")
    if not parts:
        parts.append("조건에 맞는 종목이 바뀌지 않았어요.")
    parts.append("이 데이터로는 이유까지는 알 수 없어요.")
    return {
        "headline": "기준을 바꾼 결과를 비교했어요",
        "what_changed": f"{changes}.",
        "comparison": [
            {"label": LABELS[0], "before": f"{b['passed_count']}개", "after": f"{a['passed_count']}개", "note": "기준에 따라 종목 수가 달라져요."},
            {"label": LABELS[1], "before": _pct(b["avg_return_pct"]), "after": _pct(a["avg_return_pct"]), "note": "수익률은 배당을 뺀 주가 기준이에요."},
            {"label": LABELS[2], "before": _pct(b["up_ratio_pct"], False), "after": _pct(a["up_ratio_pct"], False), "note": "기간 동안 오른 종목의 비율이에요."},
            {"label": LABELS[3], "before": _pct(b["avg_max_drawdown_pct"]), "after": _pct(a["avg_max_drawdown_pct"]), "note": "중간에 내려간 폭의 평균이에요."},
        ],
        "stock_changes": " ".join(parts),
        "cautions": ["이번 결과는 한 구간만 본 거예요. 다른 기간에는 달라질 수 있어요.",
                     "조건에 맞는 종목 수가 적으면 몇 개 종목의 움직임에 결과가 크게 흔들릴 수 있어요.",
                     "과거 결과는 앞으로를 보장하지 않아요."],
        "think_about": ["수익률, 종목 수, 하락 폭 중 나는 무엇이 더 중요한가요?",
                        "기간을 바꿔서 같은 질문을 다시 해 보면 어떨까요?"],
    }


def write_report(sim: dict, principle_name: str = "", locked_names: list[str] | None = None) -> tuple[dict, str]:
    """(리포트, 출처). 출처는 "llm" 또는 "template"."""
    payload = {k: sim[k] for k in ("period_months", "period", "universe", "changes", "before", "after",
                                   "dropped_stocks", "added_stocks", "data_notes")}
    payload = {"principle_name": principle_name, **payload, "locked_indicators": locked_names or []}
    allowed = json.dumps(payload, ensure_ascii=False)
    user = f"[입력 데이터]\n{allowed}\n\n위 데이터로 리포트를 작성해 주세요."
    for _ in range(3):  # 처음 1회 + 재요청 2회
        try:
            report = complete_json(SYSTEM, user, sample="llm_report.json", provider="anthropic", max_tokens=4096)
        except ValueError:  # JSON이 깨졌으면 재요청
            continue
        except Exception:  # 키 없음·시간 초과·연결 실패 등은 템플릿으로 대체
            break
        if not check(report, allowed):
            return report, "llm"
    return template(sim), "template"
