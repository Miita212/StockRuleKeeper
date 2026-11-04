"""H4-a 시드(지표 1~7 중심) 만들기. 사람이 쓰는 '말 → 정답' 쌍을 jsonl로 저장한다.

실행: python -X utf8 build_seed_1-7.py   (같은 폴더에 seed_1-7.jsonl 생성)
검증: python -X utf8 validate_data.py --master-dir ../../byungjun/data --input seed_1-7.jsonl

정답 규칙 (byungjun 의 H1-0 마스터 양식, H3-0 되묻기 정책을 따른다. 아래 결정은 모두 [제안], 팀 확인 필요)
- 값과 지표가 둘 다 분명하면 되묻지 않고 확정(T4). 정답은 시트 예시 E06 / yappang 조립 형식과 같은 **20개 세트**:
  말한 지표는 source=user, 나머지는 마스터 기본값 source=default, anchors=말한 지표. (처음에는 말한 지표만 적었으나
  yappang 의 생성·조립 도구가 20개 세트라 한 가지 형식으로 맞췄다.)
- 지표는 정해졌는데 값이 없으면 되묻기(T1, VALUE_MISSING). 선택지 3개와 메시지는 H3-a 파일(byungjun)에서 읽는다.
- 말이 여러 지표로 갈리면 지표 후보를 되묻기(T2, AMBIGUOUS_INDICATOR), 후보는 최대 4개.
  "안전한/튼튼한" 후보 = 1·2·4·18 (H3-0 6장 기준, yappang 사전의 2·3·4 대신).                (결정 1)
  그냥 "적자 회사"는 영업이익(5)·매출순이익률(7)을 후보로 되묻는다.                          (결정 2)
- 20개 밖 지표와 종목 추천·예측 요청은 거절(T5, T6).
- 부등호는 마스터의 operator / allowed_operators 안에서만 쓴다. 금액은 억원 숫자.
  이하 <= / 미만 < / 이상 >= / 초과·넘는 > 를 구분해서 쓴다(byungjun 의 같은 방향 두 부등호 허용, cfc5d2c 이후).
  "안 넘는/넘으면 곤란"은 이하(<=), "넘게 안 떨어진"은 이상(>=) 쪽으로 해석한다.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BJ = HERE.parent.parent / "byungjun" / "data"

# yappang 의 assemble_s1_s2.py SYSTEM 과 같게 맞춘다 (최종 학습 형식은 팀 합의 후 확정)
SYSTEM = ('너는 투자 원칙 점검 앱의 도우미야. 사용자의 말을 지표 20개 기준 JSON으로 바꿔. '
          'JSON만 출력하고, 종목 추천이나 수익 예측은 하지 않아.')


def load():
    master, opts = {}, {}
    for f in BJ.glob("*indicator_master*.json"):
        for r in json.loads(f.read_text(encoding="utf-8")):
            master[r["id"]] = r
    for f in BJ.glob("*clarify_options*.json"):
        for r in json.loads(f.read_text(encoding="utf-8")):
            opts[r["id"]] = r
    return master, opts


MASTER, OPTS = load()


def ind(i, value, op=None):
    m = MASTER[i]
    return {"id": i, "operator": op or m["operator"], "value": value, "unit": m["unit"], "source": "user"}


def confirm(*inds):
    """E06 형식(yappang 의 gold_full 과 같음): 말한 지표는 source=user, 나머지 지표는 마스터 기본값 source=default,
    anchors 는 말한 지표 id. 기본값 항목에는 기간(period_months)을 붙이지 않는다."""
    said = {x["id"]: x for x in inds}
    full = []
    for i in range(1, 21):
        m = MASTER[i]
        full.append(said[i] if i in said else
                    {"id": i, "operator": m["operator"], "value": m["default"], "unit": m["unit"], "source": "default"})
    return {"indicators": full, "anchors": sorted(said)}


def clarify_value(i):
    o = OPTS[i]
    return {"needs_clarification": True, "reason": "VALUE_MISSING", "indicator_id": i,
            "message": o["clarify_message"],
            "options": [{"level": x["level"], "label": x["label"], "value": x["value"]} for x in o["options"]]}


def ambiguous(message, ids):
    return {"needs_clarification": True, "reason": "AMBIGUOUS_INDICATOR", "message": message,
            "candidates": [{"id": i, "name": MASTER[i]["ui_name"]} for i in ids]}


def refuse(message):
    return {"refusal": True, "message": message, "indicators": []}


SAFE = ambiguous("안전하다고 볼 수 있는 기준이 여러 가지예요. 어떤 걸로 볼까요?", [1, 2, 4, 18])
DEBT = ambiguous("빚이 많다는 건 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?", [1, 2, 3])
LOAN = ambiguous("대출이 많다는 건 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?", [1, 2])
INTEREST = ambiguous("이자 부담은 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?", [1, 2, 3])
LOSS = ambiguous("적자는 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?", [5, 7])
WELL = ambiguous("본업이 잘 된다는 건 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?", [5, 7])
EARN = ambiguous("잘 번다는 건 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?", [5, 6, 7])
STEADY = ambiguous("이익이 꾸준하다는 건 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?", [5, 6, 7])
FAIL = ambiguous("위험하다는 건 여러 가지로 볼 수 있어요. 어떤 걸로 볼까요?", [4, 5, 6])
NO_PICK = "저는 종목을 추천하지 않아요. 내 원칙에 맞는지는 판정서에서 확인해 볼 수 있어요."
NO_FUTURE = "저는 앞으로 오를지 내릴지는 말씀드릴 수 없어요. 원칙에 맞는 기준을 같이 정해 볼 수 있어요."


def no_metric(name, hint):
    return refuse(f"{name}는 아직 쓰지 않는 지표예요. {hint}")


# (유형, 사용자 말, 정답, 메모)  ※ 같은 정답의 말투·오타 변형은 한 줄씩 따로 쓴다
SEEDS = [
    # ---- 1 부채비율 (<= %)
    ("단일", "부채비율 100% 이하인 회사만 보여줘", confirm(ind(1, 100)), "값·지표 분명 → 확정"),
    ("단일", "부채비율 100% 미만인 회사만 보여줘", confirm(ind(1, 100, "<")), "'미만' = <. 이하(<=)와 구분"),
    ("단일", "빚이 자기 돈의 절반 이하인 회사가 좋아요", confirm(ind(1, 50)), "'절반'=50%, 자기 돈 대비 빚=부채비율"),
    ("단일", "부채비율이 200%를 넘으면 곤란해요", confirm(ind(1, 200)), "'넘으면 곤란' → <= 200"),
    ("단일", "빚이 자기 돈보다 많지 않은 회사", confirm(ind(1, 100)), "부채가 자본과 같거나 적음 → <= 100"),
    ("단일 + 오타", "부채비율 100프로 이하 회사만 볼래여", confirm(ind(1, 100)), "프로=%, 오타"),
    ("되묻기(값 없음)", "빚 많은 회사는 피하고 싶어", clarify_value(1), "E05. 지표는 정해졌고 값이 없음"),
    ("되묻기(값 없음) + 오타", "빛 많은 회사는 피하구 싶어요", clarify_value(1), "같은 정답, 오타·말투"),
    ("되묻기(값 없음)", "빚더미 회사는 싫어", clarify_value(1), "비유 표현"),
    ("되묻기(값 없음)", "레버리지 높은 회사는 거르고 싶어요", clarify_value(1), "영문 약어 표현"),
    ("되묻기(값 없음) + 오타", "부채 많은곳은 시러요", clarify_value(1), "오타·반말"),
    # ---- 2 차입금의존도 (<= %)
    ("단일", "차입금의존도 30% 이하 회사", confirm(ind(2, 30)), "확정"),
    ("단일", "빌린 돈 비중이 자산의 20%를 안 넘는 회사", confirm(ind(2, 20)), "'안 넘는' → <= 20"),
    ("되묻기(값 없음)", "은행 돈으로 버티는 회사는 싫어", clarify_value(2), "비유 표현"),
    ("되묻기(값 없음)", "차입금 의존도 낮은 회사가 좋아", clarify_value(2), "값 없음"),
    ("되묻기(지표 모호)", "대출 많은 회사는 피하고 싶어", LOAN, "yappang 사전: 부채비율(1)·차입금의존도(2)와 겹침"),
    # ---- 3 EBITDA/금융비용 (>= 배)
    ("단일", "번 돈으로 이자를 3배 이상은 낼 수 있는 회사", confirm(ind(3, 3)), "확정"),
    ("단일", "번 돈이 이자의 3배를 넘는 회사", confirm(ind(3, 3, ">")), "'넘는' = 초과(>)"),
    ("단일", "이자도 못 내는 회사는 빼줘", confirm(ind(3, 1)), "번 돈이 이자보다 적으면 못 냄 → >= 1배"),
    ("단일", "이자 보상 5배 이상 되는 회사만", confirm(ind(3, 5)), "이자보상배율 표현이지만 3번으로 연결(정의 차이는 팀 확인)"),
    ("되묻기(값 없음)", "이자 갚을 능력이 되는 회사가 좋아요", clarify_value(3), "값 없음"),
    ("되묻기(지표 모호)", "이자 부담이 큰 회사는 싫어요", INTEREST, "yappang 사전: 1·2 와 겹침"),
    # ---- 4 자본잠식률 (<= %)
    ("단일", "자본잠식 안 된 회사만 볼래요", confirm(ind(4, 0)), "자본잠식률 0 이하 = 자본이 깎이지 않음"),
    ("단일", "자본을 까먹은 회사는 빼줘", confirm(ind(4, 0)), "'까먹은' 회사 제외 → <= 0"),
    ("단일", "자본잠식률 10% 이하인 회사", confirm(ind(4, 10)), "확정"),
    ("되묻기(값 없음)", "자기 돈이 다 닳은 회사는 피할래요", clarify_value(4), "값 없음. 4번은 보통≠default 예외 지표(H3-0)"),
    ("되묻기(지표 모호)", "망하기 직전인 회사는 싫어요", FAIL, "yappang 사전: 모호, 하나로 확정하지 말고 되묻기"),
    # ---- 5 영업이익 (> 억원, 허용 > 와 <=)
    ("단일", "본업에서 적자 나는 회사는 빼고 싶어요", confirm(ind(5, 0)), "E03/E08"),
    ("단일", "영업 적자 회사는 싫어요", confirm(ind(5, 0)), "영업 적자 제외 → > 0"),
    ("단일", "영업이익이 흑자인 회사만", confirm(ind(5, 0)), "흑자 = > 0"),
    ("단일", "영업이익이 1000억 넘는 회사", confirm(ind(5, 1000)), "'넘는' = 초과(>)"),
    ("단일", "영업이익 1000억 이상인 회사", confirm(ind(5, 1000, ">=")), "'이상' = >=. 마스터가 같은 방향 두 부등호를 허용하면서 가능"),
    ("단일", "영업이익 500억은 넘어야죠", confirm(ind(5, 500)), "초과"),
    ("되묻기(값 없음)", "영업이익 많이 나는 회사가 좋아", clarify_value(5), "금액 기준 필요. 5번은 보통≠default 예외 지표"),
    ("되묻기(지표 모호)", "적자 회사는 빼줘", LOSS, "결정 2: 영업적자/순이익 적자 모호 → 되묻기"),
    ("되묻기(지표 모호)", "본업이 잘 되는 회사", WELL, "yappang 사전: 포괄 표현"),
    # ---- 6 연속 영업흑자 연수 (>= 년)
    ("단일", "3년 연속 흑자인 회사", confirm(ind(6, 3)), "확정"),
    ("단일", "5년 연속 영업이익이 난 회사", confirm(ind(6, 5)), "확정"),
    ("단일 + 오타", "3년 연속 영업이익 흑자인 회사만 볼래요", confirm(ind(6, 3)), "영업 흑자 연속 3년"),
    ("되묻기(값 없음)", "적자를 낸 적이 없는 회사가 좋아", clarify_value(6), "연수 값 없음"),
    ("되묻기(값 없음)", "꾸준히 흑자 내는 회사", clarify_value(6), "yappang 사전 일상어"),
    ("되묻기(값 없음) + 오타", "몇년째 계속 흑자인 회사", clarify_value(6), "오타·띄어쓰기"),
    ("되묻기(지표 모호)", "해마다 이익이 나는 회사", STEADY, "yappang 사전: 이익 종류 모호(5·7)"),
    # ---- 7 매출순이익률 (>= %)
    ("단일", "100원 팔면 10원 이상 남는 회사가 좋아", confirm(ind(7, 10)), "10%로 환산"),
    ("단일", "매출순이익률 5% 이상인 회사", confirm(ind(7, 5)), "확정"),
    ("단일", "이익률이 2%도 안 되는 회사는 싫어", confirm(ind(7, 2)), "'2%도 안 되면 제외' → >= 2"),
    ("되묻기(값 없음)", "순이익률 높은 회사가 좋아요", clarify_value(7), "값 없음"),
    ("되묻기(값 없음)", "팔아서 남는 게 많은 회사", clarify_value(7), "일상어"),
    ("되묻기(값 없음) + 오타", "마진 좋은 회사만 보고싶어", clarify_value(7), "20개 중에는 매출순이익률만 있어 7로 연결"),
    # ---- 복수 지표 확정
    ("복수", "부채비율 100% 이하이고 3년 연속 영업흑자인 회사", confirm(ind(1, 100), ind(6, 3)), "지표 2개"),
    ("복수", "빚이 자기 돈의 절반 이하면서 영업이익 흑자인 회사", confirm(ind(1, 50), ind(5, 0)), "지표 2개"),
    ("복수", "자본잠식 안 되고 이자를 3배 이상 낼 수 있는 회사", confirm(ind(4, 0), ind(3, 3)), "지표 2개"),
    ("복수", "영업이익 1000억 넘고 매출순이익률 5% 이상인 회사", confirm(ind(5, 1000), ind(7, 5)), "지표 2개"),
    ("복수", "차입금의존도 30% 이하, 부채비율 100% 이하, 5년 연속 흑자인 회사",
     confirm(ind(2, 30), ind(1, 100), ind(6, 5)), "지표 3개"),
    # ---- 모호(포괄 표현)
    ("되묻기(지표 모호)", "안전한 회사가 좋아요", SAFE, "E07. 후보는 H3-0 '안전한' 묶음(1·2·4·18)"),
    ("되묻기(지표 모호) + 오타", "안전한 회사 위주로 볼래여", SAFE, "같은 정답, 오타"),
    ("되묻기(지표 모호)", "재무구조가 튼튼한 회사", SAFE, "'안전한'과 같은 묶음"),
    ("되묻기(지표 모호)", "빚 때문에 위험한 회사는 싫어요", DEBT, "H3-0 '빚 많은' 묶음(1·2·3)"),
    ("되묻기(지표 모호)", "수익성 좋은 회사", EARN, "H3-0 '잘 버는' 묶음(5·7·6)"),
    # ---- 거절
    ("거절", "ROE 15% 이상인 회사만 보여줘",
     no_metric("ROE", "수익성은 매출순이익률이나 영업이익으로 볼 수 있어요."), "E09. 20개 밖 지표"),
    ("거절", "유동비율 200% 넘는 회사 찾아줘",
     no_metric("유동비율", "빚 부담은 부채비율이나 차입금의존도로 볼 수 있어요."), "20개 밖 지표"),
    ("거절", "EPS가 높은 회사만 보여줘",
     no_metric("EPS", "번 돈은 영업이익이나 매출순이익률로 볼 수 있어요."), "20개 밖 지표"),
    ("거절", "삼성전자 지금 사도 돼?", refuse(NO_PICK), "E15. 종목 추천 요청"),
    ("거절", "내일 오를 종목 하나만 알려줘", refuse(NO_FUTURE), "예측 요청"),
]


def record(seed_id, kind, user, answer, note):
    """시드 한 줄. messages 는 학습·검증용, text/output/id 는 yappang build_prompts.py --seeds 가 읽는 필드."""
    ids = set(answer.get("anchors", []))
    if "indicator_id" in answer:
        ids.add(answer["indicator_id"])
    ids |= {c["id"] for c in answer.get("candidates", [])}
    return {
        "type": "SEED", "seed_id": seed_id, "id": seed_id, "kind": kind, "note": note, "indicator_ids": sorted(ids),
        "text": user, "output": answer,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user},
                     {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}],
    }


def main():
    out = HERE / "seed_1-7.jsonl"
    lines = []
    for n, (kind, user, answer, note) in enumerate(SEEDS, 1):
        lines.append(json.dumps(record(f"H4a-{n:03d}", kind, user, answer, note), ensure_ascii=False))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    kinds = {}
    for k, *_ in SEEDS:
        kinds[k.split(" + ")[0]] = kinds.get(k.split(" + ")[0], 0) + 1
    print(f"{len(lines)}개 저장: {out}")
    print("유형별:", kinds)


if __name__ == "__main__":
    main()
