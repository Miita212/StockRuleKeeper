"""fixed-5-hk 만들기: yappang fixed-4를 바탕으로 라벨을 고치고 보강 문장을 더한다 (hyeonkyeong, 2026-11-09).

입력 (읽기만 함): members/yappang/train_model_q4b/data/{train,val}_fixed4.jsonl, *_meta_fixed4.jsonl, test_set.jsonl
출력 (이 폴더):   train_fixed5_hk.jsonl, val_fixed5_hk.jsonl, *_meta_fixed5_hk.jsonl,
                  holdout_new_hk.jsonl (새 시험, 학습에 안 씀), changes_fixed5_hk.csv, report_fixed5_hk.json

바꾸는 것 (README.md에 기준과 이유):
  A  anchors 채우기: 추출 답에 anchors가 없으면 source가 user·inferred인 지표 id로 채운다
  R1 '싸다'류 지표 모호 후보를 [PER, PBR] 하나로 통일 (자산 대비 → PBR 값 되묻기, 이익 대비 → PER 값 되묻기)
  R2 '남기는/남는/마진' 지표 모호 [영업이익, 매출순이익률] → 매출순이익률 값 되묻기
  R3 '배당 많이/두둑/넉넉…' 지표 모호 [배당수익률, 연속 배당] → 배당수익률 값 되묻기
  AUG-REF  20개 밖 개념 거절 보강, AUG-CON 값/모호 경계 보강 (aug_sentences.py)
R1~R3는 한 턴 대화만 바꾼다. 여러 턴 대화는 뒤 턴이 앞 후보에 맞춰져 있어서 그대로 두고 CSV에 '미변경'으로 남긴다.

사용: python3 -I -X utf8 build_fixed5_hk.py
"""
import collections
import csv
import difflib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent / "yappang" / "train_model_q4b" / "data"
sys.path.insert(0, str(HERE))
from aug_sentences import CONTRAST, HOLDOUT, REFUSE  # noqa: E402

SYSTEM = "너는 투자 원칙 점검 앱의 도우미야. 사용자의 말을 지표 20개 기준 JSON으로 바꿔. JSON만 출력하고, 종목 추천이나 수익 예측은 하지 않아."


def read(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def dumps(o):
    return json.dumps(o, ensure_ascii=False)


def parse(s):
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


def batchim(word):
    ch = word.strip()[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    return ch in "LMNR0136780"  # 영문·숫자 끝(대략): 받침 있는 소리


def eun(w):
    return w + ("은" if batchim(w) else "는")


def ina(w):
    return w + ("이나" if batchim(w) else "나")


def ro(w):
    ch = w.strip()[-1]
    rieul = "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 == 8
    return w + ("으로" if batchim(w) and not rieul else "로")


def norm(s):
    return re.sub(r"[\s.,!?~]|요$", "", s)


# ---------- 기존 데이터에서 표준 형식 모으기 ----------
train, val = read(SRC / "train_fixed4.jsonl"), read(SRC / "val_fixed4.jsonl")
train_meta, val_meta = read(SRC / "train_meta_fixed4.jsonl"), read(SRC / "val_meta_fixed4.jsonl")
test = read(SRC / "test_set.jsonl")

LABEL = {}          # id → 후보 이름
VAL_MSG = {}        # id → 가장 흔한 값 되묻기 전체 (message, options)
DEFAULTS = None     # 기본값 20개
cnt_label, cnt_val = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
for r in train:
    for x in r["messages"]:
        if x["role"] != "assistant":
            continue
        o = parse(x["content"])
        if not isinstance(o, dict):
            continue
        for c in o.get("candidates") or []:
            if "id" in c:
                cnt_label[c["id"]][c.get("label") or c.get("name")] += 1
        if o.get("reason") == "VALUE_MISSING" and "period_months" not in o and "known" not in o:
            cnt_val[o["indicator_id"]][dumps({"message": o["message"], "options": o["options"]})] += 1
        if DEFAULTS is None and "indicators" in o and "anchors" in o and len(o["indicators"]) == 20:
            DEFAULTS = o["indicators"]
LABEL = {i: c.most_common(1)[0][0] for i, c in cnt_label.items()}
VAL_MSG = {i: json.loads(c.most_common(1)[0][0]) for i, c in cnt_val.items()}
DEFAULTS = [dict(x, source="default") for x in DEFAULTS]
DEFAULTS[4] = {"id": 5, "operator": ">", "value": 0, "unit": "억원", "source": "default"}  # 영업이익 기본값
UNIT = {x["id"]: x["unit"] for x in DEFAULTS}


def val_answer(i, lead=None):
    """값 되묻기 정답. lead를 주면 메시지 첫 문장만 바꾼다."""
    v = VAL_MSG[i]
    msg = v["message"] if lead is None else lead + " " + v["message"].split(". ", 1)[-1]
    return {"needs_clarification": True, "reason": "VALUE_MISSING", "indicator_id": i, "message": msg, "options": v["options"]}


def amb_answer(topic, ids):
    n = "두 가지로" if len(ids) == 2 else "여러 지표로"
    return {"needs_clarification": True, "reason": "AMBIGUOUS_INDICATOR", "message": f"{eun(topic)} {n} 볼 수 있어요. 어떤 걸로 볼까요?",
            "candidates": [{"id": i, "label": LABEL[i]} for i in ids]}


def ref_answer(concept, a, b):
    if concept == "종목 추천":
        msg = "저는 종목을 추천하지 않아요. 내 원칙에 맞는지는 판정서에서 확인해 볼 수 있어요."
    elif concept == "예측":
        msg = "저는 앞으로 오를지 내릴지는 말씀드릴 수 없어요. 원칙에 맞는 기준을 같이 정해 볼 수 있어요."
    else:
        msg = f"{eun(concept)} 아직 쓰지 않는 지표예요. {ina(a)} {ro(b)} 볼 수 있어요."
    return {"refusal": True, "message": msg, "indicators": []}


def ext_answer(items):
    ind = [dict(x) for x in DEFAULTS]
    for i, op, v in items:
        ind[i - 1] = {"id": i, "operator": op, "value": v, "unit": UNIT[i], "source": "user"}
    return {"indicators": ind, "anchors": [i for i, _, _ in items]}


def ids_of(o):
    return sorted(c["id"] for c in o.get("candidates") or [] if "id" in c)


# ---------- 라벨 고치기 ----------
CHEAP = re.compile(r"싸|싼|저평가|저렴|헐값|비싼|비싸|고평가|고가|가격이 높|값이 높|높은 가격|가격이 낮|가격이 착|예산")
NOT_CHEAP = re.compile(r"가성비|가격 대비|고점|최고가")
ASSET = re.compile(r"자산|장부|청산")
EARN = re.compile(r"이익|번 돈|버는 돈|실적|수익")
MARGIN = re.compile(r"남기|남는|남겨|마진")
DIV_MUCH = re.compile(r"배당.*(많|두둑|넉넉|쏠쏠|빵빵|짭짤|후하|높)")
DIV_STEADY = re.compile(r"꾸준|오래|연속|계속|해마다|매년|끊")

changes = []


def fix_rows(rows, metas, split):
    out = collections.Counter()
    for n, (r, m) in enumerate(zip(rows, metas)):
        msgs = r["messages"]
        if msgs[0]["content"] != SYSTEM:
            continue
        single = len(msgs) == 3
        for k, x in enumerate(msgs):
            if x["role"] != "assistant":
                continue
            o = parse(x["content"])
            if not isinstance(o, dict):
                continue
            user = msgs[k - 1]["content"]
            new, rule = None, None
            # A: anchors
            if "indicators" in o and not o.get("refusal") and "anchors" not in o:
                ids = [i["id"] for i in o["indicators"] if i.get("source") in ("user", "inferred")]
                if ids:
                    new, rule = dict(o, anchors=ids), "A anchors 채움"
            # R1~R3: 한 턴, 지표 모호, 영역 단계 아님
            elif o.get("reason") == "AMBIGUOUS_INDICATOR" and not o.get("stage"):
                ids = ids_of(o)
                if set(ids) in ({10, 11}, {10, 11, 16}) and CHEAP.search(user) and not NOT_CHEAP.search(user):
                    if ASSET.search(user) and EARN.search(user):  # 둘 다 말하면 고르게 둔다
                        cand = None if ids == [10, 11] else dict(o, message="싸다고 볼 수 있는 기준이 두 가지예요. 어떤 걸로 볼까요?",
                                                                 candidates=[{"id": 10, "label": LABEL[10]}, {"id": 11, "label": LABEL[11]}])
                        rule = "R1 싸다 후보 [10,11]"
                    elif ASSET.search(user):
                        cand, rule = val_answer(11, "자산에 비해 주가가 싼지는 PBR로 볼 수 있어요."), "R1 자산 대비 → PBR 값 되묻기"
                    elif EARN.search(user):
                        cand, rule = val_answer(10, "이익에 비해 주가가 싼지는 PER로 볼 수 있어요."), "R1 이익 대비 → PER 값 되묻기"
                    elif ids != [10, 11]:
                        cand, rule = dict(o, message="싸다고 볼 수 있는 기준이 두 가지예요. 어떤 걸로 볼까요?",
                                          candidates=[{"id": 10, "label": LABEL[10]}, {"id": 11, "label": LABEL[11]}]), "R1 싸다 후보 [10,11]"
                    else:
                        cand = None
                    if cand is not None:
                        new = cand
                elif ids == [5, 7] and MARGIN.search(user) and "이자" not in user:
                    new, rule = val_answer(7, "이익이 남는 정도는 매출순이익률로 볼 수 있어요."), "R2 남는 이익 → 매출순이익률 값 되묻기"
                elif ids == [12, 13] and DIV_MUCH.search(user) and not DIV_STEADY.search(user):
                    new, rule = val_answer(12, "배당을 많이 주는지는 최근 12개월 현금배당수익률로 볼 수 있어요."), "R3 배당 많이 → 배당수익률 값 되묻기"
                if new is not None and not single:
                    changes.append([split, n, rule + " (여러 턴이라 미변경)", user, x["content"], ""])
                    out[rule + " (여러 턴, 미변경)"] += 1
                    new = None
                    continue
            if new is not None:
                changes.append([split, n, rule, user, x["content"], dumps(new)])
                x["content"] = dumps(new)
                m.setdefault("_fixed5_hk", []).append(rule.split()[0])
                out[rule] += 1
    return out


stat_train = fix_rows(train, train_meta, "train")
stat_val = fix_rows(val, val_meta, "val")

# ---------- 보강 ----------
existing = {norm(x["content"]) for r in train + val for x in r["messages"] if x["role"] == "user"}
test_norm = [norm(t["text"]) for t in test]
hold_norm = [norm(h[-1]) for h in HOLDOUT]
dropped = collections.Counter()


def too_close(text, pool, th):
    t = norm(text)
    return max((difflib.SequenceMatcher(None, t, p).ratio() for p in pool), default=0) >= th


def add(text, answer, kind):
    if norm(text) in existing:
        dropped["기존과 같음"] += 1
        return
    if too_close(text, test_norm, 0.75):
        dropped["시험(test_set)과 비슷"] += 1
        return
    if too_close(text, hold_norm, 0.75):
        dropped["새 시험(holdout)과 비슷"] += 1
        return
    existing.add(norm(text))
    train.append({"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text},
                               {"role": "assistant", "content": dumps(answer)}]})
    train_meta.append({"type": "AUG5", "kind": kind, "_source": "hyeonkyeong/data_fixed5_hk/aug_sentences.py"})


n_before = len(train)
for concept, a, b, texts in REFUSE:
    for t in texts:
        add(t, ref_answer(concept, a, b), "AUG-REF 20개 밖 개념 거절")
TOPIC = {(10, 11): "싸다는 건", (12, 13): "배당은"}
for (kind, target), texts in CONTRAST:
    for t in texts:
        if kind == "VAL":
            add(t, val_answer(target), f"AUG-CON 값 되묻기 {target}")
        else:
            topic = TOPIC[tuple(target)]
            ans = amb_answer(topic.replace("는 건", "").replace("은", ""), target)
            ans["message"] = f"{topic} 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?"
            add(t, ans, f"AUG-CON 지표 모호 {target}")
n_aug = len(train) - n_before

# ---------- 새 시험 세트 ----------
holdout = []
for h in HOLDOUT:
    kind, text = h[0], h[-1]
    if kind == "EXT":
        out = ext_answer(h[1])
    elif kind == "VAL":
        out = val_answer(h[1])
    elif kind == "AMB":
        topic = {(10, 11): "싸다는 건", (8, 9): "성장은", (12, 13): "배당은"}[tuple(h[1])]
        out = {"needs_clarification": True, "reason": "AMBIGUOUS_INDICATOR", "message": f"{topic} 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?",
               "candidates": [{"id": i, "label": LABEL[i]} for i in h[1]]}
    else:
        out = ref_answer(h[1], h[2], h[3])
    tid = f"N{len(holdout) + 1:03d}"
    holdout.append({"test_id": tid, "source": "holdout_hk", "orig_id": tid, "eval_id": tid, "id": tid, "kind": kind, "text": text,
                    "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}], "output": out})
leak = [h["text"] for h in holdout if norm(h["text"]) in existing or too_close(h["text"], test_norm, 0.75)]

# ---------- 쓰기 ----------
def write(p, rows):
    with open(HERE / p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(dumps(r) + "\n")


write("train_fixed5_hk.jsonl", train)
write("val_fixed5_hk.jsonl", val)
write("train_meta_fixed5_hk.jsonl", train_meta)
write("val_meta_fixed5_hk.jsonl", val_meta)
write("holdout_new_hk.jsonl", holdout)
with open(HERE / "changes_fixed5_hk.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["split", "row", "rule", "user", "before", "after"])
    w.writerows(changes)


def count_answers(rows):
    c = collections.Counter()
    for r in rows:
        o = parse(r["messages"][-1]["content"])
        if not isinstance(o, dict):
            c["설명(텍스트)"] += 1
        elif o.get("refusal"):
            c["거절"] += 1
        elif o.get("reason") == "AMBIGUOUS_INDICATOR":
            c["지표 모호"] += 1
        elif o.get("reason") == "VALUE_MISSING":
            c["값 되묻기"] += 1
        elif o.get("reason") == "PERIOD_MISSING":
            c["기간 되묻기"] += 1
        else:
            c["추출·수정"] += 1
    return dict(c)


no_anchor = sum(1 for r in train + val for x in r["messages"] if x["role"] == "assistant"
                and isinstance(parse(x["content"]), dict) and "indicators" in parse(x["content"])
                and not parse(x["content"]).get("refusal") and "anchors" not in parse(x["content"])
                and any(i.get("source") in ("user", "inferred") for i in parse(x["content"])["indicators"]))
report = {"train": len(train), "val": len(val), "holdout": len(holdout), "aug_added": n_aug, "aug_dropped": dict(dropped),
          "changes_train": dict(stat_train), "changes_val": dict(stat_val), "train_answers": count_answers(train),
          "extract_without_anchors_left": no_anchor, "holdout_close_to_train_or_test": leak}
json.dump(report, open(HERE / "report_fixed5_hk.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False, indent=1))
