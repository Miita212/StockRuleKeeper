"""학습 데이터 fixed-2 생성 (q4b-v3용). fixed-1 에 아래 두 가지를 더한다.
  1. 되묻기 후보 키 통일: candidates 의 {"id","name"} → {"id","label"} (평가 정답·백엔드 우선 키와 맞춤, area 후보는 그대로)
  2. 평가에서 약했던 유형의 보강 샘플(템플릿 생성, 아래 ADD_* 참고)
       - 지표 번호 혼동(1·2, 8·9, 5·7, 10·11, 12·13, 19·20 등) 단일 지표 문장
       - 같은 값이 반복되는 복수 지표 문장 ("A와 B 모두 20% 이상")
       - "지표 모호" 되묻기 (새 표현, 메시지는 문장의 말을 따라 쓴다)
       - "20개 밖" 거절 중 약어 없는 서술형, 매매 시점·종목 추천 거절 변형
  평가 문장(eval_set.jsonl, H5-*.jsonl)과 겹치는 문장은 넣지 않고, 평가에 나온 개념어(FORBID)는 쓰지 않는다 → 평가가 암기로 올라가지 않게.

실행 (members/yappang 에서)
  python -I -X utf8 data/scripts/build_v3_data.py
입력: data/train_data/{train,val}_fixed(.jsonl|_meta_fixed.jsonl)   (fixed-1)
출력: data/train_data/{train,val}_fixed2.jsonl, *_meta_fixed2.jsonl, v3_report.json, v3_conflict_audit.csv, v3_additions_preview.csv
"""
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAPPANG = HERE.parents[1]
DATA = YAPPANG / "data"
OUT = DATA / "train_data"
sys.path.insert(0, str(HERE))
import data_fixes  # noqa: E402

rng = random.Random(42)

# 평가에 나온 개념어: 보강 문장에 쓰지 않는다
FORBID = ["현금 많", "현금 보유", "쌓아둔", "배당 성장", "배당성장", "EPS", "ROA", "ROIC", "PEG", "MACD", "기관", "가성비", "튼튼", "잘 버는", "망할", "빚 걱정",
          "이익이 늘어", "배당주", "롤러코스터", "규모가 큰", "하나 골라", "하나만 골라", "지금 팔아야", "제일 좋은", "마이너스는 아닌", "흑자인"]


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------- 한글 조사 ----------
def jong(w):
    for ch in reversed(w):
        if "가" <= ch <= "힣":
            return (ord(ch) - 0xAC00) % 28
    return None  # 한글 아님


def batchim(w):
    j = jong(w)
    return bool(j)


def eun(w):
    return w + ("은" if batchim(w) else "는")


def wa(w):
    return w + ("과" if batchim(w) else "와")


def ina(w):
    return w + ("이나" if batchim(w) else "나")


def ro(w):
    j = jong(w)
    return w + ("로" if (not j or j == 8) else "으로")


def irago(w):
    return w + ("이라고" if batchim(w) else "라고")


# ---------- 마스터·기본 형식 ----------
MASTER = {}
for f in sorted(DATA.glob("H1-?_indicator_master_*.json")):
    for m in json.loads(f.read_text(encoding="utf-8")):
        MASTER[m["id"]] = m
train_fixed1 = read_jsonl(OUT / "train_fixed.jsonl")
meta_fixed1 = read_jsonl(OUT / "train_meta_fixed.jsonl")
val_fixed1 = read_jsonl(OUT / "val_fixed.jsonl")
vmeta_fixed1 = read_jsonl(OUT / "val_meta_fixed.jsonl")
SYSTEM = train_fixed1[0]["messages"][0]["content"]
DEFAULTS = None
for r in train_fixed1:
    c = r["messages"][-1]["content"]
    if c.startswith('{"indicators"'):
        j = json.loads(c)
        if len(j["indicators"]) == 20 and all(x["source"] == "default" or True for x in j["indicators"]):
            DEFAULTS = {x["id"]: {k: x[k] for k in ("id", "operator", "value", "unit")} for x in j["indicators"] if x["source"] == "default"}
            if len(DEFAULTS) == 19:
                missing = [i for i in range(1, 21) if i not in DEFAULTS][0]
                DEFAULTS[missing] = {k: next(y for y in j["indicators"] if y["id"] == missing)[k] for k in ("id", "operator", "value", "unit")}
                # 이 행의 user 지표 값은 기본값이 아닐 수 있다 → 마스터로 되돌린다
                m = MASTER[missing]
                DEFAULTS[missing] = {"id": missing, "operator": m["operator"], "value": m["default"], "unit": m["unit"]}
            if len(DEFAULTS) == 20:
                break
assert DEFAULTS and len(DEFAULTS) == 20, "기본 지표 20개를 찾지 못했다"
for i, d in DEFAULTS.items():
    assert d["operator"] == MASTER[i]["operator"] or i in (5,), (i, d, MASTER[i]["operator"])


def make_ind(users):
    """users: {id: (op, value)} → 20개 지표 JSON 문자열"""
    inds = []
    for i in range(1, 21):
        d = dict(DEFAULTS[i])
        if i in users:
            d["operator"], d["value"] = users[i]
            d["source"] = "user"
        else:
            d["source"] = "default"
        inds.append({"id": d["id"], "operator": d["operator"], "value": d["value"], "unit": d["unit"], "source": d["source"]})
    return json.dumps({"indicators": inds}, ensure_ascii=False)


def num(v):
    return str(int(v)) if float(v) == int(v) else str(v)


# ---------- 평가 문장 ----------
EVAL_TEXTS = set()
for p in [YAPPANG / "train_model_q4b" / "data" / "eval_set.jsonl"] + sorted(DATA.glob("H5-*.jsonl")):
    for r in read_jsonl(p):
        for v in r.values():
            if isinstance(v, str):
                EVAL_TEXTS.add(v.strip())
EXISTING = {data_fixes.first_user(r) for r in train_fixed1 + val_fixed1}

# ---------- 1) 단일 지표 (번호 혼동 보강) ----------
SINGLE_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 19, 20]
WEIGHT = {1: 3, 2: 3, 5: 3, 7: 3, 8: 3, 9: 3, 10: 2, 11: 2, 12: 2, 13: 2, 19: 2, 20: 2}  # 혼동이 보인 지표는 더 많이
WORD = {">=": "이상", "<=": "이하", "<": "미만", ">": "초과"}
UNIT_SPOKEN = {"%": "퍼센트", "배": "배", "년": "년", "억원": "억원", "개월": "개월"}


def val_choices(i):
    m = MASTER[i]
    d, lo, hi = m["default"], m["min"], m["max"]
    if i == 4:
        base = [10, 20, 30, 50]
    elif i == 5:
        base = [50, 100, 300, 500, 1000]
    elif d in (0, None):
        base = [x for x in (1, 5, 10, 20)]
    else:
        base = [d * 0.5, d * 0.8, d, d * 1.5, d * 2]
    out = []
    for v in base:
        if MASTER[i]["unit"] in ("년", "개월"):
            v = max(1, int(round(v)))
        else:
            v = round(v * 2) / 2 if v < 10 else int(round(v))   # 0.5 단위, 10 이상은 정수
            v = int(v) if float(v) == int(v) else v
        if lo <= v <= hi and v not in out:
            out.append(v)
    return out


NAME_OVERRIDE = {5: ["영업이익"], 12: ["배당수익률", "12개월 배당수익률"], 13: ["연속 배당 연수", "연속 배당"], 15: [], 16: [], 17: []}


def names_of(i):
    """문장에 쓸 지표 이름. 마스터 이름과 별칭을 쓰되, 뜻이 틀어지는 별칭('흑자' 등)은 NAME_OVERRIDE 로 바꾼다."""
    if i in NAME_OVERRIDE:
        return NAME_OVERRIDE[i]
    m = MASTER[i]
    ns = [m["name"]] + [a for a in m.get("alias", []) if a != m["name"]]
    return list(dict.fromkeys(ns))


def cond_text(op, v, u):
    """('20%', '이상') 대신 문장 조각을 돌려준다."""
    vs = num(v) + u
    if op == ">":
        if rng.random() < 0.5:
            return f"{vs}{'를' if not batchim(UNIT_SPOKEN.get(u, u)) else '을'} 넘는", "넘는"
    return f"{vs} {WORD[op]}", WORD[op]


FRAMES_END = {  # 조각 뒤에 붙는 말. '넘는'은 명사형 어미라 따로
    "end": ["인 회사만 보여줘", "인 종목 찾아줘", "인 곳 위주로 볼래요", "인 기업으로 골라줘", "인 주식만 담고 싶어요"],
    "넘는": [" 회사만 보여줘", " 종목 찾아줘", " 곳 위주로 볼래요", " 기업으로 골라줘"],
}
PRE = ["", "", "", "내 기준은 ", "나는 ", "저는 "]


def single_sentence(i):
    m = MASTER[i]
    ops = [o for o in m["allowed_operators"] if o in WORD]
    op = rng.choice(ops)
    v = rng.choice(val_choices(i))
    n = rng.choice(names_of(i))
    cond, kind = cond_text(op, v, m["unit"])
    pre = rng.choice(PRE)
    if pre:
        text = f"{pre}{n} {cond}{'야' if kind != '넘는' else ' 곳이 좋아'}" if kind != "넘는" else f"{pre}{n} {cond} 곳이 좋아"
        if kind != "넘는":
            text = f"{pre}{n} {cond}{rng.choice(['이면 좋겠어', '이어야 해', '인 회사가 좋아'])}"
    else:
        tail = rng.choice(FRAMES_END["넘는"] if kind == "넘는" else FRAMES_END["end"])
        text = f"{n} {cond}{tail}"
    return text, {i: (op, v)}


def gen_single(n_target):
    pool = [i for i in SINGLE_IDS for _ in range(WEIGHT.get(i, 1))]
    out, seen = [], set()
    tries = 0
    while len(out) < n_target and tries < n_target * 40:
        tries += 1
        i = rng.choice(pool)
        text, users = single_sentence(i)
        if text in seen:
            continue
        seen.add(text)
        out.append((text, users, "S1", [i]))
    return out


# ---------- 2) 복수 지표 (같은 값 반복 포함) ----------
PAIRS = [(8, 9), (1, 2), (5, 7), (10, 11), (12, 13), (3, 7), (6, 9), (14, 19), (14, 20), (19, 20), (2, 3), (1, 3), (7, 9), (8, 14),
         (4, 1), (10, 8), (11, 7), (12, 1), (13, 6), (5, 8)]
TRIPLES = [(1, 3, 9), (8, 9, 7), (10, 12, 14), (2, 5, 8), (1, 6, 12), (11, 7, 19)]


def one_cond(i, op, v, short=False):
    m = MASTER[i]
    n = rng.choice(names_of(i))
    return f"{n} {num(v)}{m['unit']} {WORD[op]}"


def gen_multi(n_target):
    out, seen = [], set()
    tries = 0
    while len(out) < n_target and tries < n_target * 60:
        tries += 1
        ids = list(rng.choice(PAIRS if rng.random() < 0.8 else TRIPLES))
        rng.shuffle(ids)
        mode = rng.choice(["same", "same", "diff", "diff"])
        ms = [MASTER[i] for i in ids]
        users, parts = {}, []
        if mode == "same" and len({m["unit"] for m in ms}) == 1 and len(ids) == 2:
            op = rng.choice([o for o in ms[0]["allowed_operators"] if o in WORD and o in ms[1]["allowed_operators"]] or [None])
            vc = [v for v in val_choices(ids[0]) if v in val_choices(ids[1])]
            if op is None or not vc:
                continue
            v = rng.choice(vc)
            a, b = names_of(ids[0]), names_of(ids[1])
            na, nb = rng.choice(a), rng.choice(b)
            text = rng.choice([
                f"{wa(na)} {nb} 모두 {num(v)}{ms[0]['unit']} {WORD[op]}인 회사",
                f"{wa(na)} {nb} 둘 다 {num(v)}{ms[0]['unit']} {WORD[op]}이면 좋겠어요",
                f"{na}도 {nb}도 {num(v)}{ms[0]['unit']} {WORD[op]}인 종목 찾아줘",
            ])
            users = {ids[0]: (op, v), ids[1]: (op, v)}
        else:
            ok = True
            for i, m in zip(ids, ms):
                ops = [o for o in m["allowed_operators"] if o in WORD]
                op = rng.choice(ops)
                v = rng.choice(val_choices(i))
                users[i] = (op, v)
                parts.append(one_cond(i, op, v))
            vals = [users[i][1] for i in ids]
            if len(set(vals)) < len(vals):  # 값이 같아지면 same 템플릿이 아니므로 값 충돌을 피한다
                continue
            conn = rng.choice([("이고 ", "인 회사"), ("이면서 ", "인 종목"), ("이고, ", "인 기업만 보여줘")])
            text = parts[0] + conn[0] + (parts[1] if len(parts) == 2 else parts[1] + conn[0] + parts[2]) + conn[1]
        if text in seen:
            continue
        seen.add(text)
        out.append((text, users, "S2", sorted(users)))
    return out


# ---------- 3) 지표 모호 되묻기 (새 표현) ----------
# (후보 지표들, 메시지에 쓸 말, [문장...])
AMB = [
    ((8, 9), "성장", ["커 가는 회사가 좋아요", "계속 자라는 기업 위주로 볼래요", "성장세 좋은 곳만 담고 싶어", "앞으로 크는 종목을 찾고 있어요", "쑥쑥 자라는 회사 보여줘"]),
    ((8, 9), "실적이 좋아진다는 건", ["실적이 나아지는 회사 위주로", "갈수록 실적 좋아지는 기업이면 돼요", "실적 개선되는 종목 찾아줘"]),
    ((1, 2, 4, 18), "안전하다고", ["믿을 만한 회사가 좋아요", "든든한 기업 위주로 볼래요", "탈 없는 종목만 담고 싶어", "마음 편한 주식을 찾고 있어요", "리스크가 적은 회사 보여줘", "오래 들고 가도 되는 종목"]),
    ((10, 11, 16), "싸다고", ["가격이 착한 주식 위주로", "값싼 종목만 보여줘요", "헐값인 회사 찾아줘", "저렴한 주식을 찾고 있어요", "할인 중인 종목 위주로 볼래요"]),
    ((10, 11), "싸다고", ["이익이나 자산에 비해 싼 주식", "벌어들이는 것보다 값이 낮은 종목"]),
    ((12, 13), "배당", ["꼬박꼬박 챙겨 주는 회사가 좋아요", "주주에게 잘 나눠 주는 기업 위주로", "나눠 주는 걸 좋아하는 종목 찾아줘", "주주 환원이 좋은 곳 보여줘"]),
    ((5, 7), "이익", ["돈 잘 남기는 회사만", "남는 게 많은 기업 위주로 볼래요", "장사 잘하는 곳이 좋아", "수익 좋은 종목 찾아줘"]),
    ((5, 6, 7), "잘 번다는 건", ["벌이가 좋은 기업이 좋아요", "꾸준히 돈 버는 회사 위주로", "수입이 탄탄한 곳 보여줘", "돈 되는 장사를 하는 회사"]),
    ((15, 19, 20), "관심이 몰린다는 건", ["핫한 종목이 좋아요", "사람들이 몰리는 주식 위주로", "화제가 되는 종목 찾아줘"]),
    ((19, 20), "거래가 활발하다는 건", ["거래 많은 종목 위주로 볼래요", "손바뀜이 잦은 주식이 좋아", "사고파는 사람이 많은 종목"]),
    ((16, 17), "바닥권", ["바닥 다진 종목 보여줘", "많이 눌려 있는 주식 위주로", "저점 근처에 있는 종목이 좋아요"]),
    ((14, 19, 20), "인기가 많다는 건", ["인기 있는 종목 위주로 볼래요", "다들 찾는 주식 보여줘"]),
    ((1, 2), "대출이 많다는 건", ["대출이 많은 회사는 피하고 싶어요", "빌려 쓴 돈이 많은 곳은 별로예요"]),
    ((1, 2, 3), "이자 부담은", ["이자 걱정이 적은 회사 위주로", "이자 낼 힘이 있는 기업이 좋아요"]),
    ((10, 11, 15), "거품은", ["거품 낀 주식은 싫어요", "너무 오른 종목은 피하고 싶어"]),
    ((15, 20), "급등은", ["갑자기 뛰는 종목 찾아줘", "확 오르는 주식 위주로 볼래요"]),
    ((15, 16), "폭락은", ["확 빠진 종목 보여줘", "크게 떨어진 주식 위주로"]),
    ((8, 14), "커진다는 건", ["덩치가 불어나는 회사 위주로", "몸집을 키우는 기업이 좋아요"]),
    ((4, 5, 6), "위험하다는 건", ["망가질 것 같은 회사는 피하고 싶어요", "위태로워 보이는 기업은 빼고 싶어"]),
]


AMB_STEMS = {
    ((8, 9), "성장"): ["커 가는 회사", "자라는 기업", "성장세 좋은 종목", "앞으로 클 회사", "쑥쑥 크는 주식"],
    ((8, 9), "실적이 좋아진다는 건"): ["실적이 나아지는 회사", "갈수록 실적 좋아지는 기업", "실적 개선되는 종목"],
    ((1, 2, 4, 18), "안전하다고"): ["믿을 만한 회사", "든든한 기업", "탈 없는 종목", "마음 편한 주식", "리스크 적은 회사", "오래 들고 갈 종목"],
    ((10, 11, 16), "싸다고"): ["가격이 착한 주식", "값싼 종목", "헐값인 회사", "저렴한 주식", "할인 중인 종목"],
    ((12, 13), "배당"): ["꼬박꼬박 챙겨 주는 회사", "주주에게 잘 나눠 주는 기업", "주주 환원 좋은 곳", "나눠 주기 좋아하는 종목"],
    ((5, 7), "이익"): ["돈 잘 남기는 회사", "남는 게 많은 기업", "장사 잘하는 곳", "수익 좋은 종목"],
    ((5, 6, 7), "잘 번다는 건"): ["벌이가 좋은 기업", "꾸준히 돈 버는 회사", "수입이 탄탄한 곳", "돈 되는 장사 하는 회사"],
    ((15, 19, 20), "관심이 몰린다는 건"): ["핫한 종목", "사람들이 몰리는 주식", "화제가 되는 종목"],
    ((19, 20), "거래가 활발하다는 건"): ["거래 많은 종목", "손바뀜이 잦은 주식", "사고파는 사람 많은 종목"],
    ((16, 17), "바닥권"): ["바닥 다진 종목", "많이 눌려 있는 주식", "저점 근처 종목"],
    ((14, 19, 20), "인기가 많다는 건"): ["인기 있는 종목", "다들 찾는 주식", "사랑받는 종목"],
    ((1, 2), "대출이 많다는 건"): ["대출이 많은 회사", "빌려 쓴 돈이 많은 곳", "대출 의존이 큰 기업"],
    ((1, 2, 3), "이자 부담은"): ["이자 걱정이 적은 회사", "이자 낼 힘이 있는 기업", "이자 부담 가벼운 곳"],
    ((10, 11, 15), "거품은"): ["거품 낀 주식", "너무 오른 종목", "과열된 주식"],
    ((15, 20), "급등은"): ["갑자기 뛰는 종목", "확 오르는 주식", "치고 나가는 종목"],
    ((15, 16), "폭락은"): ["확 빠진 종목", "크게 떨어진 주식", "무너진 종목"],
    ((8, 14), "커진다는 건"): ["덩치가 불어나는 회사", "몸집을 키우는 기업", "점점 커지는 곳"],
    ((4, 5, 6), "위험하다는 건"): ["망가질 것 같은 회사", "위태로워 보이는 기업", "불안한 곳"],
}


def amb_message(group, kw):
    n = len(group)
    if kw.endswith("건") or kw.endswith("은") and kw not in ("성장", "배당", "이익", "바닥권"):
        head = kw
    else:
        head = eun(kw)
    form = rng.random()
    if kw == "안전하다고" or kw == "싸다고":
        return f"{kw} 볼 수 있는 기준이 {'두 가지예요' if n == 2 else '여러 가지예요'}. 어떤 걸로 볼까요?"
    if n == 2:
        return f"{head} 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?" if form < 0.7 else f"{head} 두 지표로 갈려요. 어떤 걸로 볼까요?"
    return f"{head} 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?" if form < 0.7 else f"{head} 여러 가지로 갈려요. 어떤 걸로 볼까요?"


AMB_FRAMES = ["{s}", "{s}만 보여줘", "{s} 위주로 볼래요", "{s} 찾아줘", "{s}{iga} 좋아요", "{s}{eul} 고르고 싶어요"]


def gen_amb():
    out = []
    for group, kw, texts in AMB:
        for t in texts:   # 손으로 쓴 완성 문장
            out.append((t, group, kw))
        for s in AMB_STEMS.get((group, kw), []):   # 명사구 × 틀
            for fr in AMB_FRAMES:
                out.append((fr.format(s=s, iga="이" if batchim(s) else "가", eul="을" if batchim(s) else "를"), group, kw))
    res = []
    for t, group, kw in out:
        msg = amb_message(group, kw)
        ans = {"needs_clarification": True, "reason": "AMBIGUOUS_INDICATOR", "message": msg,
               "candidates": [{"id": i, "label": MASTER[i]["name"]} for i in group]}
        res.append((t, json.dumps(ans, ensure_ascii=False), "S2", list(group)))
    return res


# ---------- 4) 거절 (20개 밖 서술형, 매매 시점, 종목 추천) ----------
# (개념, 문장들, 안내 문장). 개념어는 한글만 쓴다(조사 규칙 단순화).
OOS = [
    ("영업현금흐름", ["영업으로 들어오는 돈이 많은 회사만", "영업현금흐름 좋은 회사 보여줘", "장사해서 현금이 잘 들어오는 기업 찾아줘", "영업활동으로 번 현금 기준으로 골라줘"],
     "영업이익이나 매출순이익률로 볼 수 있어요."),
    ("자기자본이익률", ["자기 돈으로 얼마나 버는지가 높은 회사", "자기자본이익률 높은 곳만 보여줘", "내 자본 대비 이익이 큰 기업 찾아줘"],
     "수익성은 매출순이익률이나 영업이익으로 볼 수 있어요."),
    ("재고자산회전율", ["재고가 빨리 팔리는 회사", "재고자산회전율 높은 기업 찾아줘", "물건이 잘 팔려 재고가 안 쌓이는 곳 보여줘"],
     "매출액 증가율이나 영업이익 증가율로 볼 수 있어요."),
    ("외국인 지분율", ["외국인 지분이 많은 회사만 보여줘", "외국인 지분율 높은 종목 찾아줘", "외국 투자자 비중이 큰 기업 골라줘"],
     "시가총액이나 20일 평균 거래대금으로 볼 수 있어요."),
    ("목표주가", ["증권사 목표주가가 높은 종목", "목표주가 대비 싼 주식 찾아줘", "애널리스트가 좋게 보는 회사 보여줘"],
     "싼 정도는 PER이나 PBR로 볼 수 있어요."),
    ("신용등급", ["신용등급 좋은 회사만 보여줘", "신용등급이 높은 기업 찾아줘", "채권 등급이 탄탄한 곳 위주로"],
     "재무 건전성은 부채비율이나 이자보상배율로 볼 수 있어요."),
    ("연구개발비", ["연구개발비를 많이 쓰는 회사", "연구개발비 비중 높은 기업 찾아줘", "기술 투자에 돈 많이 쓰는 곳 보여줘"],
     "성장은 매출액 증가율이나 영업이익 증가율로 볼 수 있어요."),
    ("무상증자", ["무상증자 한 적 있는 회사", "무상증자 이력이 있는 종목 찾아줘", "주식을 공짜로 나눠 준 기업 보여줘"],
     "재무 상태는 자본잠식률이나 부채비율로 볼 수 있어요."),
    ("대주주 지분율", ["대주주 지분이 높은 회사만 보여줘", "대주주 지분율 큰 종목 찾아줘", "최대주주가 많이 들고 있는 기업"],
     "회사 규모는 시가총액으로 볼 수 있어요."),
    ("환율 영향", ["환율이 오르면 이익 보는 회사", "환율 영향 적은 기업 찾아줘", "달러가 강할 때 좋은 종목 보여줘"],
     "수익성은 매출순이익률이나 영업이익으로 볼 수 있어요."),
    ("분기 배당", ["분기마다 배당 주는 회사만", "분기 배당 하는 종목 찾아줘", "한 해에 네 번 배당하는 기업 보여줘"],
     "배당은 12개월 배당수익률이나 연속 배당 연수로 볼 수 있어요."),
    ("단기차입금", ["단기차입금 비중이 낮은 회사", "단기차입금 적은 기업 보여줘", "곧 갚아야 할 돈이 적은 곳 찾아줘"],
     "빌린 돈은 부채비율이나 차입금의존도로 볼 수 있어요."),
    ("이자수익", ["이자수익이 큰 회사", "이자수익 많은 기업 찾아줘", "이자로 버는 돈이 많은 곳 보여줘"],
     "수익성은 영업이익이나 매출순이익률로 볼 수 있어요."),
    ("정부 지원금", ["정부 지원금 받는 회사", "정부 지원금이 많은 기업 찾아줘", "나라에서 돈 받는 곳 보여줘"],
     "재무 상태는 부채비율이나 영업이익으로 볼 수 있어요."),
]
SUFFIX_OOS = ["", "", " 알려줘", "만 보여줘"]
TIMING = ["지금 이 주식 사도 될까?", "오늘 팔아야 하나요?", "언제 들어가는 게 좋을까?", "이 종목 지금 손절할까요?", "내일 사면 오를까, 말까?",
          "타이밍 좋은 때 알려줘", "지금이 매수 적기인지 알려줘", "보유 종목 지금 정리할까요?", "언제 팔면 이득일까?", "바닥인지 아닌지 보고 사라고 해줘"]
RECO = ["내 원칙에 맞는 종목 중에 제일 나은 걸로 골라줘", "원칙 통과한 회사 중에서 하나만 찍어줘", "어떤 종목을 사면 좋을지 하나 알려줘", "추천 종목 세 개만 알려줘",
        "내 기준 통과한 것 중 뭐가 제일 좋아?", "사야 할 주식 하나만 골라 줘", "이 중에 뭘 사면 돼?", "가장 유망한 종목 이름만 알려줘", "오를 만한 종목 알려줘",
        "찜해 둘 만한 회사 하나 추천해줘"]


def common_msg(substr):
    c = Counter()
    for r in train_fixed1:
        a = r["messages"][-1]["content"]
        if a.startswith("{") and substr in a:
            c[a] += 1
    return c.most_common(1)[0][0] if c else None


REFUSE_TIMING = common_msg("알려 드리지 않아요")
REFUSE_RECO = common_msg("추천하지 않아요")


def gen_refuse():
    out = []
    for term, texts, guide in OOS:
        for t in texts:
            if rng.random() < 0.25:
                t = t + rng.choice(SUFFIX_OOS)
            msg = f"{eun(term)} 아직 쓰지 않는 지표예요. {guide}"
            ans = json.dumps({"refusal": True, "message": msg, "indicators": []}, ensure_ascii=False)
            out.append((t, ans, "S5", []))
    for t in TIMING:
        out.append((t, REFUSE_TIMING, "S5", []))
    for t in RECO:
        out.append((t, REFUSE_RECO, "S5", []))
    return out


# ---------- 조립 ----------
def to_row(user, ans):
    return {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}, {"role": "assistant", "content": ans}]}


def build():
    adds, dropped = [], []
    for text, users, typ, ids in gen_single(260) + gen_multi(140):
        adds.append((text, make_ind(users), typ, ids, "단일" if typ == "S1" else "복수"))
    for text, ans, typ, ids in gen_amb():
        adds.append((text, ans, typ, ids, "되묻기(지표 모호)"))
    for text, ans, typ, ids in gen_refuse():
        adds.append((text, ans, typ, ids, "거절"))
    kept, seen = [], set()
    for text, ans, typ, ids, kind in adds:
        text = text.strip()
        if text in EVAL_TEXTS:
            dropped.append((text, "평가 문장과 같음")); continue
        if text in EXISTING:
            dropped.append((text, "기존 학습 문장과 같음")); continue
        if text in seen:
            dropped.append((text, "추가분 중복")); continue
        bad = next((w for w in FORBID if w in text or w in ans), None)
        if bad:
            dropped.append((text, f"평가 개념어 {bad}")); continue
        seen.add(text)
        kept.append((text, ans, typ, ids, kind))
    return kept, dropped


def check_josa(ans):
    """안내 문구의 흔한 조사 오류 검사: '률나 ', '액는 아직'"""
    if re.search(r"(률|율|배율|성향|액)(나|는) ", ans):
        return True
    m = re.search(r'"message": "(.+?)(은|는) 아직', ans)
    return bool(m and jong(m.group(1)) is not None and (m.group(2) == "은") != batchim(m.group(1)))


def unify_candidates(rows):
    n = 0
    for r in rows:
        a = r["messages"][-1]["content"]
        if not a.startswith("{") or "candidates" not in a:
            continue
        j = json.loads(a)
        if json.dumps(j, ensure_ascii=False) != a:
            continue
        ch = False
        for c in j.get("candidates") or []:
            if "name" in c and "label" not in c:
                c["label"] = c.pop("name")
                ch = True
        if ch:
            r["messages"][-1]["content"] = json.dumps(j, ensure_ascii=False)
            n += 1
    return n


def audit_conflicts():
    """같은 말이 한쪽은 되묻기(AMBIGUOUS), 다른 쪽은 값 되묻기(VALUE_MISSING)로 학습된 곳을 찾는다. 사람이 판단할 목록."""
    ov = {}
    for f in sorted(DATA.glob("H2-?_synonyms_*.csv")):
        for row in csv.DictReader(open(f, encoding="utf-8-sig")):
            if row["겹침_지표번호"].strip():
                ov[row["표현"]] = (row["지표번호"], row["겹침_지표번호"])
    by = defaultdict(lambda: {"VALUE_MISSING": [], "AMBIGUOUS_INDICATOR": []})
    exact = defaultdict(set)
    for r in train_fixed1 + val_fixed1:
        a = r["messages"][-1]["content"]
        if not a.startswith("{"):
            continue
        j = json.loads(a)
        u = data_fixes.first_user(r)
        rs = j.get("reason")
        if rs in ("VALUE_MISSING", "AMBIGUOUS_INDICATOR"):
            exact[u].add((rs, tuple(sorted(c.get("id") for c in j.get("candidates", []))) or (j.get("indicator_id"),)))
            for e in ov:
                if e in u:
                    by[e][rs].append(u)
    rows = []
    for e, d in by.items():
        if d["VALUE_MISSING"] and d["AMBIGUOUS_INDICATOR"]:
            rows.append(["표현 충돌", e, "/".join(ov[e]), len(d["VALUE_MISSING"]), len(d["AMBIGUOUS_INDICATOR"]),
                         " | ".join(d["VALUE_MISSING"][:2]), " | ".join(d["AMBIGUOUS_INDICATOR"][:2])])
    for u, s in exact.items():
        reasons = {x[0] for x in s}
        if len(reasons) > 1:
            rows.append(["같은 문장 정답 충돌", u, "", "", "", str(sorted(s)), ""])
    return rows


def main():
    train, tmeta, val, vmeta = [json.loads(json.dumps(x)) for x in (train_fixed1, meta_fixed1, val_fixed1, vmeta_fixed1)]
    n_u = unify_candidates(train) + unify_candidates(val)

    kept, dropped = build()
    bad = [(t, a) for t, a, *_ in kept if check_josa(a)]
    if bad:
        sys.exit(f"[중단] 조사 의심 문구 {len(bad)}건: {bad[:3]}")
    # 추가분에도 기존 수정 규칙(부등호 경계 대조)을 적용해 본다: 결과가 바뀌면 생성 규칙 오류
    prev = []
    n_add_tr = n_add_va = 0
    changed = 0
    for k, (text, ans, typ, ids, kind) in enumerate(kept):
        row = to_row(text, ans)
        nr, act, note = data_fixes.fix_row(row, typ)
        if act:
            changed += 1
            prev.append([text, act, note])
        meta = {"type": typ, "indicator_ids": ids, "style": "v3", "kind": kind, "_source": "data/scripts/build_v3_data.py"}
        if k % 20 == 7:      # 약 5%는 검증용
            val.append(row); vmeta.append(meta); n_add_va += 1
        else:
            train.append(row); tmeta.append(meta); n_add_tr += 1
    if changed:
        print(f"[주의] 생성 문장 {changed}건이 부등호 점검에서 바뀌거나 제외 대상:", prev[:5])
        sys.exit("[중단] 생성 규칙을 고친 뒤 다시 실행")

    # 검사
    tf = {data_fixes.first_user(r) for r in train}
    vf = {data_fixes.first_user(r) for r in val}
    problems = []
    if tf & vf:
        problems.append(f"train/val 첫 질문 겹침 {len(tf & vf)}건")
    if (tf | vf) & EVAL_TEXTS:
        problems.append(f"평가 문장 섞임 {len((tf | vf) & EVAL_TEXTS)}건")
    if len(train) != len(tmeta) or len(val) != len(vmeta):
        problems.append("대화·메타 줄 수 불일치")
    for r in train + val:
        a = r["messages"][-1]["content"]
        if a.startswith("{"):
            try:
                json.loads(a)
            except ValueError:
                problems.append("정답 JSON 파싱 실패"); break
    # 쓰기
    report = {"입력": "data/train_data/*_fixed* (fixed-1)", "후보 키 name→label 변환 대화 수": n_u,
              "추가": {"train": n_add_tr, "val": n_add_va, "종류별": dict(Counter(k[4] for k in kept))},
              "제외된 후보": dict(Counter(d[1] for d in dropped)), "결과": {}, "검사 문제": problems}
    for nm, rows, metas in (("train", train, tmeta), ("val", val, vmeta)):
        for fname, data in ((f"{nm}_fixed2.jsonl", rows), (f"{nm}_meta_fixed2.jsonl", metas)):
            with open(OUT / fname, "w", encoding="utf-8", newline="\n") as f:
                for x in data:
                    f.write(json.dumps(x, ensure_ascii=False) + "\n")
            report["결과"][fname] = {"lines": len(data), "sha256": sha(OUT / fname)}
    (OUT / "v3_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(OUT / "v3_additions_preview.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["종류", "유형", "입력", "정답(앞 120자)"])
        for text, ans, typ, ids, kind in kept:
            w.writerow([kind, typ, text, ans[:120] if not ans.startswith('{"indicators"') else
                        ";".join(f"{x['id']}{x['operator']}{x['value']}{x['unit']}" for x in json.loads(ans)["indicators"] if x["source"] == "user")])
    aud = audit_conflicts()
    with open(OUT / "v3_conflict_audit.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["구분", "표현/문장", "겹침 지표", "VALUE_MISSING 수", "AMBIGUOUS 수", "VALUE_MISSING 예", "AMBIGUOUS 예"])
        w.writerows(aud)
    print(json.dumps({k: report[k] for k in ("후보 키 name→label 변환 대화 수", "추가", "제외된 후보", "검사 문제")}, ensure_ascii=False, indent=1))
    print("학습", len(train), "검증", len(val), "| 충돌 점검 목록", len(aud), "건")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
