"""학습 데이터 수정 규칙(fixed-1, 2026-11-08). 병합된 대화(messages + 메타)에 적용한다.

고치는 것
  1. 정답의 부등호 경계 오류: 입력 문장의 '이상/이하/미만/초과/넘는'과 정답 연산자가 어긋난 것
     (단일 지표는 문장 하나, 복수 지표(S2)는 숫자 바로 뒤의 부등호 말로 지표를 찾아 맞춘다).
     부정·조건 표현("넘지 않는", "제외", "문제 있어요" 등)은 자동으로 건드리지 않는다.
     부정 표현 중 사람이 판단한 것은 data_fixes_rules.json 의 neg_fix, 자동 규칙이 놓친 것은 explicit 로 지정한다.
  2. 안내 문구의 조사 오류: '배당성향는 아직 쓰지' → '배당성향은'
제외하는 것
  - data_fixes_rules.json 의 drop_texts: 제외 문장인데 포함 조건으로 반전된 것, 문장이 깨진 것
  - 복수 지표에서 방향을 고쳐야 하는데 대상이 지표 16·17(해석이 모호)인 것

규칙 파일은 입력 문장(첫 user 발화) 기준이라 병합 순서·분할이 달라져도 같은 문장에 같게 적용된다.
쓰는 곳: build_train_data.py. 점검 근거: train_model_q4b/data/train_audit_issues.csv
"""
import json
import re
from pathlib import Path

RULES = json.loads((Path(__file__).with_name("data_fixes_rules.json")).read_text(encoding="utf-8"))
DROP_TEXT = set(RULES["drop_texts"])
NEGFIX = dict(RULES["neg_fix"])
EXPL = {t: {int(k): v for k, v in d.items()} for t, d in RULES["explicit"].items()}

KW = {"이상": ">=", "이하": "<=", "미만": "<", "초과": ">", "넘": ">"}
NEG = re.compile(r"않|안 |제외|빼|없애|지워|아니|못|말고|싫|피하")
# 조건·금지·부정적 어감이라 키워드와 정답 방향이 달라도 정상인 문장
IMPLICIT = re.compile(r"문제|곤란|위험|나쁘|피해|주의|좋지|걱정|부담|불안|빠진|빠지|떨어|내려|하락|감소|신중|안되|안 되|줄어|넘으면|미만이면|이하이면")
UNIT_MULT = {"조": 10000, "천억": 1000, "백억": 100}
NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(천억|백억|조|억|만|%|퍼센트|배|년|개월)?")


def first_user(row):
    return row["messages"][1]["content"].strip()


def _fix_particles(msg):
    """'X는 아직'(받침 있는 X) → 'X은 아직', "'…회사'은" → "'…회사'는"."""
    def f(m):
        w = m.group(1)
        return w + ("은" if (ord(w[-1]) - 0xAC00) % 28 else "는") + " 아직"
    out = re.sub(r"^([가-힣]+)는 아직", f, msg)
    return re.sub(r"^('[^']+회사')은 ", r"\1는 ", out)


def fix_row(row, typ):
    """(새 행, 조치, 메모). 조치: None(그대로) | 'fix' | 'drop'. 입력 행은 바꾸지 않는다."""
    msgs = row["messages"]
    text = first_user(row)
    if text in DROP_TEXT:
        return row, "drop", "의미 반전/문장 불명확"
    last = msgs[-1]["content"]
    j = None
    if last.startswith("{"):
        try:
            j = json.loads(last)
        except ValueError:
            return row, None, ""
        if json.dumps(j, ensure_ascii=False) != last:
            j = None  # 직렬화가 달라지면 손대지 않는다
    notes, changed = [], False
    if j is not None and isinstance(j.get("message"), str):
        m1 = _fix_particles(j["message"])
        if m1 != j["message"]:
            j["message"] = m1
            changed = True
            notes.append("조사 수정")
    if (j is not None and isinstance(j.get("indicators"), list) and len(j["indicators"]) == 20
            and len(msgs) == 3 and typ in ("S1", "S2", "SEED")):
        users = [x for x in j["indicators"] if x.get("source") == "user"]
        kws = [k for k in KW if k in text]
        if text in EXPL:
            for x in users:
                op = EXPL[text].get(x["id"])
                if op and x["operator"] != op:
                    notes.append(f"id{x['id']} {x['operator']}→{op}")
                    x["operator"] = op
                    changed = True
        elif text in NEGFIX and len(users) == 1:
            if users[0]["operator"] != NEGFIX[text]:
                notes.append(f"id{users[0]['id']} {users[0]['operator']}→{NEGFIX[text]} (부정 표현)")
                users[0]["operator"] = NEGFIX[text]
                changed = True
        elif kws and users and not NEG.search(text) and not IMPLICIT.search(text):
            if len(users) == 1 and len(kws) == 1:
                exp = KW[kws[0]]
                if users[0]["operator"] != exp:
                    notes.append(f"id{users[0]['id']} {users[0]['operator']}→{exp}")
                    users[0]["operator"] = exp
                    changed = True
            elif len(users) >= 2:
                for kw in kws:
                    for mk in re.finditer(re.escape(kw), text):
                        nums = list(NUM_RE.finditer(text[:mk.start()].replace(",", "")))
                        if not nums or mk.start() - nums[-1].end() > 6:
                            continue
                        v = float(nums[-1].group(1)) * UNIT_MULT.get(nums[-1].group(2), 1)
                        cand = [x for x in users if float(x["value"]) == v]
                        if len(cand) != 1:
                            continue
                        x = cand[0]
                        if x["operator"] != KW[kw]:
                            if x["id"] in (16, 17):
                                return row, "drop", f"id{x['id']} 방향 해석 모호"
                            notes.append(f"id{x['id']} {x['operator']}→{KW[kw]}")
                            x["operator"] = KW[kw]
                            changed = True
    if not changed:
        return row, None, ""
    new = json.loads(json.dumps(row, ensure_ascii=False))
    new["messages"][-1]["content"] = json.dumps(j, ensure_ascii=False)
    return new, "fix", "; ".join(notes)


def apply(rows, metas=None):
    """rows(+metas)에 수정 규칙을 적용한다. 메타가 없으면 행의 type 을 쓴다.
    returns (rows, metas, log). 로그: (행번호(1부터), 유형, 조치, 입력 앞 60자, 메모)"""
    out_rows, out_metas, log = [], [], []
    for i, r in enumerate(rows):
        m = metas[i] if metas is not None else None
        typ = (m or r).get("type")
        nr, act, note = fix_row(r, typ)
        if act == "drop":
            log.append((i + 1, typ, "제외", first_user(r)[:60], note))
            continue
        if act == "fix":
            log.append((i + 1, typ, "수정", first_user(r)[:60], note))
            if m is not None:
                m = dict(m)
                m["_fix"] = note
        out_rows.append(nr)
        out_metas.append(m)
    return out_rows, out_metas, log
