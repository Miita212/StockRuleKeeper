"""fixed-6-hk 만들기: fixed-5-hk에 yappang 검증(11/09) 반영 기준을 더한다 (hyeonkyeong, 2026-11-09).

입력 (읽기만 함): ../data_fixed5_hk/{train,val}_fixed5_hk.jsonl, *_meta_fixed5_hk.jsonl, holdout_new_hk.jsonl
                  members/yappang/train_model_q4b/data/test_set.jsonl
출력 (이 폴더):   train_fixed6_hk.jsonl, val_fixed6_hk.jsonl, *_meta_fixed6_hk.jsonl, holdout_new_hk6.jsonl,
                  test_fixed6_hk.jsonl (test_set 정답 9건 수정본 + holdout, yappang 동의 전 제안용),
                  changes_fixed6_hk.csv, report_fixed6_hk.json

바꾸는 것 (README.md에 기준과 이유):
  D   "어떤 기준으로 볼까요? 아래에서 골라 주세요." 88개를 하나씩 보고 값 되묻기로 고치거나, 주제어 문구로 바꾸거나, 지운다 (GENERIC 표)
  G1  이익이 늘어나는: 모호[8,9] → 이익만 말하면 영업이익 증가율, 매출만 말하면 매출액 증가율 값 되묻기
  G2  폭락: 고점을 말하면 52주 고점 대비 값 되묻기, 그냥 폭락·많이 빠진은 모호[15,16]
  G3  규모·크기·몸집 큰: 모호[14,19] → 시가총액 값 되묻기
  G4  가성비·가격 매력: 모호[10,11,16] → 모호[10,11]
  G5  저점·바닥: 모호[16,17]·[15,17] → 52주 저점 대비 값 되묻기
  G6  잘 버는·장사 잘하는: 모호[5,6,7] → 꾸준히류가 없으면 모호[5,7]
  G7  본업: 늘어남을 말하지 않으면 영업이익 값 되묻기
  AUG6 위 기준 대조 문장 (aug_sentences6.py)
fixed-5-hk와 같이 한 턴 대화만 바꾼다.

사용: python3 -I -X utf8 build_fixed6_hk.py
"""
import collections
import csv
import difflib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
F5 = HERE.parent / "data_fixed5_hk"
TEST = HERE.parent.parent / "yappang" / "train_model_q4b" / "data" / "test_set.jsonl"
sys.path.insert(0, str(HERE))
from aug_sentences6 import AMB_MSG, CONTRAST6, N019_NEW  # noqa: E402

SYSTEM = "너는 투자 원칙 점검 앱의 도우미야. 사용자의 말을 지표 20개 기준 JSON으로 바꿔. JSON만 출력하고, 종목 추천이나 수익 예측은 하지 않아."
GENERIC_MSG = "어떤 기준으로 볼까요? 아래에서 골라 주세요."


def read(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def dumps(o):
    return json.dumps(o, ensure_ascii=False)


def parse(s):
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


def norm(s):
    return re.sub(r"[\s.,!?~]|요$", "", s)


train, val = read(F5 / "train_fixed5_hk.jsonl"), read(F5 / "val_fixed5_hk.jsonl")
train_meta, val_meta = read(F5 / "train_meta_fixed5_hk.jsonl"), read(F5 / "val_meta_fixed5_hk.jsonl")
holdout = read(F5 / "holdout_new_hk.jsonl")
test = read(TEST)

# ---------- 표준 형식 (fixed-5-hk와 같은 방식) ----------
cnt_label, cnt_val = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
for r in train:
    for x in r["messages"]:
        o = parse(x["content"]) if x["role"] == "assistant" else None
        if not isinstance(o, dict):
            continue
        for c in o.get("candidates") or []:
            if "id" in c:
                cnt_label[c["id"]][c.get("label") or c.get("name")] += 1
        if o.get("reason") == "VALUE_MISSING" and "period_months" not in o and "known" not in o:
            cnt_val[o["indicator_id"]][dumps({"message": o["message"], "options": o["options"]})] += 1
LABEL = {i: c.most_common(1)[0][0] for i, c in cnt_label.items()}
VAL_MSG = {i: json.loads(c.most_common(1)[0][0]) for i, c in cnt_val.items()}


def val_answer(i):
    v = VAL_MSG[i]
    return {"needs_clarification": True, "reason": "VALUE_MISSING", "indicator_id": i, "message": v["message"], "options": v["options"]}


def amb_answer(ids):
    return {"needs_clarification": True, "reason": "AMBIGUOUS_INDICATOR", "message": AMB_MSG[tuple(ids)],
            "candidates": [{"id": i, "label": LABEL[i]} for i in ids]}


def ids_of(o):
    return sorted(c["id"] for c in o.get("candidates") or [] if "id" in c)


# ---------- D: 일반 문구 88개 (사용자 말 → 처리). DEL = 지움(지표와 관계없는 말·질문·영어) ----------
GENERIC = {
    "바닥에 머물고 있는 주식들": ("VAL", 17), "매출이익률이 높은 기업": ("VAL", 7),
    "저평가된 주식은 할인상품처럼 느껴져요": ("AMB", [10, 11]), "운영 효율성이 낮은 회사": "DEL",
    "마지막 기회를 잃은 상태": "DEL", "성과가 점점 좋아지는 기업": ("AMB", [8, 9]), "영업적 부담이 늘어나는 회사": "DEL",
    "지속적인 수익성을 가진 기업": ("AMB", [5, 6, 7]), "영업이익이 증가하는 기업도 많아": ("VAL", 9),
    "지지선을 넘어서는 주식들": "DEL", "실적 향상이 눈에 띄는 기업": ("AMB", [8, 9]), "해마다 이익이 나는 회사들": ("VAL", 6),
    "annual profit-making company": "DEL", "이익률이 하락하는 회사": ("VAL", 7),
    "배당금이 안정적으로 지급되는 기업": ("VAL", 13), "영업적 실적을 잃고 있는 상태": "DEL",
    "영업이익이 줄어들고 있는 상황": ("VAL", 9), "주요 활동의 수익성이 높은 기업": ("AMB", [5, 7]),
    "손익 구조가 악화된 회사": "DEL", "버티고 있는 주식들": "DEL", "경쟁력 있는 수익 기반을 만든 회사": ("AMB", [5, 7]),
    "매년 수익을 창출하는 회사가 있어": ("VAL", 6), "이익률이 오래 지속되는 기업": ("VAL", 7),
    "실적 향상이 가시화되고 있는 기업": ("AMB", [8, 9]), "주요 부문에서 지속적인 성장을 이어가는 기업": ("AMB", [8, 9]),
    "성장 중인 기업들을 주목해야 해": ("AMB", [8, 9]), "비용 관리가 잘된 기업": ("AMB", [5, 7]),
    "Continuous loss-making companies": "DEL", "안정적인 수익을 기록하는 기업": ("AMB", [5, 6, 7]),
    "영업이익이 안정적인 기업": ("VAL", 6), "최근 매출이 확대되는 기업들이 주목받고 있어": ("VAL", 8),
    "업적 향상에 주목할 만한 기업": ("AMB", [8, 9]), "재무상황이 건전한 기업": ("AMB", [1, 2, 3, 4]),
    "성장 속도가 빨라진 기업": ("AMB", [8, 9]), "주식이 저평가된 상태라면 매수할 수 있을까요": "DEL",
    "Main business profitability is stable": "DEL", "지수 상승 전후에 주목할 만한 주식들": "DEL",
    "생존 가능성이 낮은 기업": "DEL", "매출순이익률이 낮은 경우": ("VAL", 7), "매출이 꾸준히 증가하는 기업": ("VAL", 8),
    "Main business shows consistent growth": "DEL", "PBR나 PER 기준으로 저평가된 주식을 찾고 있어요": ("AMB", [10, 11]),
    "하락장에서 안정을 찾는 주식들": "DEL", "매년 이익을 얻는 회사야": ("VAL", 6),
    "저평가된 주식은 시장이 무시하고 있는 건가요": "DEL", "실적 개선이 이어지고 있는 기업": ("AMB", [8, 9]),
    "영업익이 꾸준히 유지되는 회사": ("VAL", 6), "이익률이 견고한 기업": ("VAL", 7), "기대 이상으로 성과를 보이는 회사": "DEL",
    "최근 성과가 높아진 기업": ("AMB", [8, 9]), "주식이 가격이 낮아서 저평가된 걸로 보이는데요": "DEL",
    "지속적인 수익 창출을 이어가는 회사": ("AMB", [5, 6, 7]), "기본 수익이 안정적인 기업": ("AMB", [5, 6, 7]),
    "매출액 증가를 기록 중인 기업들": ("VAL", 8), "전환점 근처에서 움직이는 주식들": "DEL", "매출에서 이익이 높은 기업": ("VAL", 7),
    "주요 사업 수익성이 높은 기업": ("AMB", [5, 7]), "매출이익을 꾸준히 기록하는 기업": ("VAL", 6),
    "매출에서 이익이 많이 나는 기업": ("VAL", 7), "하락세 종료를 기다리는 주식들": "DEL", "지금 성장 중인 기업들 많아": ("AMB", [8, 9]),
    "수익을 안정적으로 낸 회사": ("AMB", [5, 6, 7]), "이익을 극대화하고 있는 회사": ("AMB", [5, 7]), "지금 성장 중인 기업 많아": ("AMB", [8, 9]),
    "영업 부채가 증가하는 회사": "DEL", "주가가 낮아서 저평가된 게 아닐 수도 있어요": "DEL", "성장세를 이어가는 기업": ("AMB", [8, 9]),
    "주식이 저평가된 상태라면 재평가될 수 있을까요": "DEL", "지속적으로 손실을 떠넘기는 회사": "DEL",
    "지속적으로 수익을 낼 수 있는 회사": ("AMB", [5, 6, 7]), "지금 기업들 중에서 성장하고 있는 곳이 많아": ("AMB", [8, 9]),
    "연속적으로 적자에서 벗어난 기업": "DEL", "지난해 수익이 늘어나는 기업들이 많아": ("AMB", [8, 9]),
    "예산을 써버린 듯한 경영 상태": "DEL", "경쟁력 있는 수익 구조를 가진 회사": ("AMB", [5, 7]), "자본잠식 위험에 처한 기업": ("VAL", 4),
    "배당 안정성 있는 기업": ("VAL", 13), "연속적으로 이익을 내는 기업들": ("VAL", 6), "지속적인 수익을 기록하는 회사": ("AMB", [5, 6, 7]),
    "영업익이 매년 증가하는 기업": ("VAL", 9), "수익성에 강점을 가진 기업": ("AMB", [5, 7]), "예산 초과로 흔들리는 회사": "DEL",
    "정기적인 수익을 기록하는 기업": ("AMB", [5, 6, 7]), "지속적인 손실이 발생하는 경우": "DEL",
    "Now, growing companies are many": "DEL", "기본적인 수익이 안정적인 기업": ("AMB", [5, 6, 7]), "연속 적자로 갈등 중인 기업": "DEL",
    "저항선 아래서 움직이는 주식들": "DEL",
}

STEADY = re.compile(r"꾸준|매년|해마다|연속|안정|지속|오래|계속|늘|한결|항상|정기|연간|년간")
GROW = re.compile(r"늘|증가|커지|커진|확장|성장|불어|키우")
SIZE = re.compile(r"규모|크기|몸집|덩치|대형|체급")
HIGH = re.compile(r"고점|최고가|꼭대기")
LOW = re.compile(r"저점|바닥|최저")

changes, deleted = [], []


def answer_of(spec):
    kind, x = spec
    return val_answer(x) if kind == "VAL" else amb_answer(x)


def rule_for(user, o):
    """한 턴 대화의 정답 o에 적용할 (새 정답, 규칙). 해당 없으면 (None, None)."""
    if o.get("reason") != "AMBIGUOUS_INDICATOR" and not (o.get("reason") in ("VALUE_MISSING", "PERIOD_MISSING")):
        return None, None
    ids = ids_of(o)
    amb = o.get("reason") == "AMBIGUOUS_INDICATOR" and not o.get("stage")
    if o.get("message") == GENERIC_MSG and user in GENERIC:
        spec = GENERIC[user]
        return ("DEL", "D 일반 문구 → 지움") if spec == "DEL" else (answer_of(spec), f"D 일반 문구 → {spec[0]} {spec[1]}")
    if amb and ids == [8, 9] and "매출" not in user and re.search(r"영업이익|영업익|이익", user) and not re.search(r"실적|성장|성과", user):
        return val_answer(9), "G1 이익 증가 → 영업이익 증가율"
    if amb and ids == [8, 9] and "매출" in user and "이익" not in user:
        return val_answer(8), "G1 매출 증가 → 매출액 증가율"
    if amb and ids == [15, 16] and HIGH.search(user):
        return val_answer(16), "G2 고점 대비 하락 → 52주 고점 대비"
    if ((amb and ids == [16, 17]) or o.get("reason") == "PERIOD_MISSING") and re.search(r"꺼진|폭락|급락|빠진|떨어진", user) \
            and not HIGH.search(user) and not LOW.search(user):
        return amb_answer([15, 16]), "G2 폭락 → 모호[15,16]"
    if amb and ids == [14, 19] and SIZE.search(user) and not GROW.search(user):
        return val_answer(14), "G3 규모 → 시가총액"
    if amb and ids == [10, 11, 16] and re.search(r"가성비|가격 매력|가격 대비", user):
        return amb_answer([10, 11]), "G4 가성비 → 모호[10,11]"
    if amb and ids in ([16, 17], [15, 17]) and LOW.search(user) and not HIGH.search(user):
        return val_answer(17), "G5 저점·바닥 → 52주 저점 대비"
    if amb and ids == [5, 6, 7] and not STEADY.search(user) and not re.search(r"적자|손실|흑자", user):
        return amb_answer([5, 7]), "G6 잘 버는 → 모호[5,7]"
    if "본업" in user and not GROW.search(user) and ((amb and ids in ([5, 7], [5, 7, 8, 9])) or
                                                   (o.get("reason") == "VALUE_MISSING" and o.get("indicator_id") == 9)):
        return val_answer(5), "G7 본업 → 영업이익"
    return None, None


def fix_rows(rows, metas, split):
    out_rows, out_metas, stat = [], [], collections.Counter()
    for n, (r, m) in enumerate(zip(rows, metas)):
        msgs = r["messages"]
        o = parse(msgs[-1]["content"]) if msgs[0]["content"] == SYSTEM else None
        if len(msgs) == 3 and isinstance(o, dict):
            user = msgs[1]["content"]
            new, rule = rule_for(user, o)
            if new == "DEL":
                changes.append([split, n, rule, user, msgs[2]["content"], ""])
                deleted.append(user)
                stat[rule] += 1
                continue
            if new is not None:
                changes.append([split, n, rule, user, msgs[2]["content"], dumps(new)])
                msgs[2]["content"] = dumps(new)
                m = dict(m, _fixed6_hk=rule.split()[0])
                stat[rule] += 1
        out_rows.append(r)
        out_metas.append(m)
    return out_rows, out_metas, stat


train, train_meta, stat_train = fix_rows(train, train_meta, "train")
val, val_meta, stat_val = fix_rows(val, val_meta, "val")

# ---------- test_set 정답 수정 제안 (yappang 파일은 건드리지 않고 이 폴더에 사본) ----------
TEST_NAME = {c["id"]: c["name"] for t in test for c in t["output"].get("candidates") or [] if "name" in c}


def amb_test(ids):
    """test_set 형식: 후보 키가 label이 아니라 name이고, 이름도 test_set에 쓰인 것"""
    o = amb_answer(ids)
    o["candidates"] = [{"id": i, "name": TEST_NAME.get(i, LABEL[i])} for i in ids]
    return o


T163 = next(t for t in test if t["test_id"] == "T163")["output"]
T199 = next(t for t in test if t["test_id"] == "T199")["output"]
TEST_FIX = {
    "T031": amb_test([5, 7]), "T228": amb_test([5, 7]),
    "T064": amb_test([10, 11]), "T229": amb_test([10, 11]),
    "T065": dict(T199, message=T199["message"].replace("본업 이익이", "이익이")),
    "T106": val_answer(18),
    "T107": T163, "T193": T163,
    "T197": amb_test([15, 16]),
}
test6, test_changes = [], []
for t in test:
    t = dict(t)
    if t["test_id"] in TEST_FIX:
        test_changes.append([t["test_id"], t["text"], dumps(t["output"]), dumps(TEST_FIX[t["test_id"]])])
        t["output"] = TEST_FIX[t["test_id"]]
    test6.append(t)

# ---------- holdout N019 교체 ----------
for h in holdout:
    if h["test_id"] == "N019":
        h["text"] = N019_NEW
        h["messages"][1]["content"] = N019_NEW

# ---------- 보강 (시험과 0.65 이상 비슷하면 뺌) ----------
existing = {norm(x["content"]) for r in train + val for x in r["messages"] if x["role"] == "user"}
train_norm = list(existing)
exam_norm = [norm(t["text"]) for t in test] + [norm(h["text"]) for h in holdout]
dropped = collections.defaultdict(list)


def sim(text, pool):
    t = norm(text)
    return max((difflib.SequenceMatcher(None, t, p).ratio() for p in pool), default=0)


n_before = len(train)
for (kind, target), texts in CONTRAST6:
    for text in texts:
        if norm(text) in existing:
            dropped["기존과 같음"].append(text)
            continue
        s = sim(text, exam_norm)
        if s >= 0.65:
            dropped["시험과 비슷(0.65 이상)"].append(f"{text} ({s:.2f})")
            continue
        existing.add(norm(text))
        ans = val_answer(target) if kind == "VAL" else amb_answer(target)
        train.append({"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text},
                                   {"role": "assistant", "content": dumps(ans)}]})
        train_meta.append({"type": "AUG6", "kind": f"AUG6 {kind} {target}", "_source": "hyeonkyeong/data_fixed6_hk/aug_sentences6.py"})
n_aug = len(train) - n_before

# holdout과 학습 사이 유사도 (0.65 이상이면 보고)
hold_close = [(h["test_id"], h["text"], round(sim(h["text"], train_norm), 2)) for h in holdout]
hold_close = [x for x in hold_close if x[2] >= 0.65]


# ---------- 쓰기 ----------
def write(p, rows):
    with open(HERE / p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(dumps(r) + "\n")


write("train_fixed6_hk.jsonl", train)
write("val_fixed6_hk.jsonl", val)
write("train_meta_fixed6_hk.jsonl", train_meta)
write("val_meta_fixed6_hk.jsonl", val_meta)
write("holdout_new_hk6.jsonl", holdout)
write("test_fixed6_hk.jsonl", test6 + holdout)
with open(HERE / "changes_fixed6_hk.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["split", "row", "rule", "user", "before", "after"])
    w.writerows(changes)
    for c in test_changes:
        w.writerow(["test_set", c[0], "TEST 정답 수정 제안", c[1], c[2], c[3]])

left_generic = sum(1 for r in train + val for x in r["messages"] if x["role"] == "assistant" and GENERIC_MSG in x["content"])
report = {"train": len(train), "val": len(val), "holdout": len(holdout), "test_fixed6": len(test6) + len(holdout),
          "aug_added": n_aug, "aug_dropped": dict(dropped), "deleted": len(deleted),
          "changes_train": dict(stat_train), "changes_val": dict(stat_val), "test_changed": [c[0] for c in test_changes],
          "generic_msg_left(여러 턴)": left_generic, "holdout_close_to_train(0.65+)": hold_close}
json.dump(report, open(HERE / "report_fixed6_hk.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False, indent=1))
