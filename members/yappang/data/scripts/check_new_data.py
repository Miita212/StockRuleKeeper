"""fixed-5 추가 데이터 검증 (다른 팀원이 만든 신규 데이터를 받았을 때 쓴다).  2026-11-09, yappang.

사용 (members/yappang 에서):
  python3 -I -X utf8 data/scripts/check_new_data.py <신규.jsonl> [--base train_model_q4b/data/train_fixed4.jsonl] [--val train_model_q4b/data/val_fixed4.jsonl]
신규 파일은 train 과 같은 형식: 한 줄에 {"messages":[system,user,assistant], ...}.
시험 문장과의 유사도 검사(9 시험 유사 문장): 띄어쓰기·문장부호를 뺀 글자열의 유사도가 --near-fail(기본 0.75) 이상이면 실패,
--near-warn(기본 0.65) 이상이면 경고. 정답 유형·지표가 같으면 '정답 같음' 표시(시험 점수를 부풀리므로 우선 확인).
체크리스트: docs/fixed5-verification-checklist.md.  실패 항목이 하나라도 있으면 종료코드 1.
"""
import argparse, collections, difflib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "train_model_q4b" / "data"
IDS = set(range(1, 21))
REASONS = {"AMBIGUOUS_INDICATOR", "VALUE_MISSING", "PERIOD_MISSING"}


def rows(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def parts(r):
    m = r["messages"]
    return m[1]["content"].strip(), m[-1]["content"]


def norm(t):
    return re.sub(r"[\s\W_]+", "", t)


def sig(o):
    """정답의 유형과 지표: 같은 시험 문장과 정답까지 같은지 보려는 용도"""
    if isinstance(o, str):
        try:
            o = json.loads(o)
        except Exception:
            return ("설명",)
    if not isinstance(o, dict):
        return ("?",)
    if o.get("refusal"):
        return ("거절",)
    if o.get("reason") == "AMBIGUOUS_INDICATOR":
        return ("모호", tuple(sorted(c.get("id") for c in o.get("candidates") or [])))
    if o.get("reason"):
        return (o["reason"], o.get("indicator_id"))
    if "changes" in o:
        return ("changes",)
    if "indicators" in o:
        return ("변환", tuple(sorted(i.get("id") for i in o["indicators"] if i.get("source") == "user")))
    return ("?",)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("new")
    ap.add_argument("--base", default=str(D / "train_fixed4.jsonl"))
    ap.add_argument("--val", default=str(D / "val_fixed4.jsonl"))
    ap.add_argument("--test", default=str(D / "test_set.jsonl"))
    ap.add_argument("--near-fail", type=float, default=0.75)
    ap.add_argument("--near-warn", type=float, default=0.65)
    a = ap.parse_args()

    new = rows(a.new)
    fails = collections.defaultdict(list)

    def bad(k, msg):
        fails[k].append(msg)

    base_txt = {parts(r)[0] for r in rows(a.base)} | {parts(r)[0] for r in rows(a.val)}
    test_txt = {r["text"].strip() for r in rows(a.test)}
    seen = collections.Counter()
    kinds = collections.Counter()
    sets_by_msg = collections.defaultdict(set)

    for i, r in enumerate(new, 1):
        tag = "행%d" % i
        try:
            user, raw = parts(r)
        except Exception:
            bad("1 형식", tag + " messages 구조"); continue
        if [m["role"] for m in r["messages"][:2]] != ["system", "user"] or r["messages"][-1]["role"] != "assistant":
            bad("1 형식", tag + " role 순서")
        seen[user] += 1
        try:
            o = json.loads(raw)
        except Exception:
            kinds["설명(텍스트)"] += 1  # 지표 설명 응답(예: '60일 변동성 뭐야?')은 JSON 이 아니다
            if raw.lstrip().startswith(("{", "[")): bad("1 형식", tag + " JSON 깨짐: " + user)
            if user in test_txt: bad("2 시험 문장 중복", tag + " " + user)
            if user in base_txt: bad("3 기존 train/val 중복", tag + " " + user)
            continue
        if user in test_txt: bad("2 시험 문장 중복", tag + " " + user)
        if user in base_txt: bad("3 기존 train/val 중복", tag + " " + user)

        if o.get("refusal"):
            kinds["거절"] += 1
            msg = o.get("message", "")
            if o.get("indicators") != []: bad("5 거절 형식", tag + " indicators 가 [] 아님")
            if "아직 쓰지 않는" in msg and not re.search(r"(으로|로) 볼 수 있어요\.$", msg): bad("6 거절 조사", tag + " " + msg)
            if re.search(r"(률|율|액|금|량)나 ", msg) or re.search(r"[가-힣]+(률|비율|보유액|증가율)는 아직", msg): bad("6 거절 조사", tag + " " + msg)
        elif o.get("needs_clarification"):
            reason = o.get("reason")
            kinds["되묻기:" + str(reason)] += 1
            if reason not in REASONS: bad("5 되묻기 형식", tag + " reason=" + str(reason))
            if reason == "AMBIGUOUS_INDICATOR":
                c = o.get("candidates") or []
                ids = [x.get("id") for x in c]
                if any(set(x) != {"id", "label"} for x in c): bad("7 후보 키", tag + " 키가 id,label 이 아님")
                if not 2 <= len(ids) <= 4: bad("7 후보 수", tag + " %d개" % len(ids))
                if ids != sorted(ids) or len(set(ids)) != len(ids) or not set(ids) <= IDS: bad("7 후보 id", tag + " %s" % ids)
                head = o.get("message", "")
                sets_by_msg[head.split("은 ")[0].split("는 ")[0][:12]].add(tuple(ids))
            if reason == "VALUE_MISSING" and o.get("indicator_id") not in IDS: bad("5 되묻기 형식", tag + " indicator_id")
        elif isinstance(o.get("changes"), list):
            kinds["원칙 수정(changes)"] += 1
        elif isinstance(o.get("indicators"), list):
            kinds["변환"] += 1
            ids20 = [x.get("id") for x in o["indicators"]]
            if sorted(ids20) != sorted(IDS): bad("8 지표 20개", tag + " id 목록이 1~20 이 아님")
            for x in o["indicators"]:
                if x.get("id") not in IDS: bad("8 지표 id", tag + " id=%s" % x.get("id"))
                if x.get("operator") not in {"<", "<=", ">", ">="}: bad("8 연산자", tag + " " + str(x.get("operator")))
                if x.get("source") not in {"user", "default"}: bad("8 source", tag + " " + str(x.get("source")))
        else:
            bad("1 형식", tag + " 알 수 없는 응답 유형")

    for t, n in seen.items():
        if n > 1: bad("4 신규 내부 중복", "%s (%d회)" % (t, n))
    # 9 시험 유사 문장: 정확히 같지 않아도 거의 같은 문장은 시험 점수를 부풀린다
    tests = [(norm(r["text"]), r["text"].strip(), sig(r.get("output"))) for r in rows(a.test)]
    near_warn = []
    for i, r in enumerate(new, 1):
        try:
            user, raw = parts(r)
        except Exception:
            continue
        nu = norm(user)
        for nt, tt, tsig in tests:
            if nu == nt or not nt or not nu:
                continue
            sm = difflib.SequenceMatcher(None, nu, nt)
            if sm.real_quick_ratio() < a.near_warn or sm.quick_ratio() < a.near_warn:
                continue
            sc = sm.ratio()
            if sc < a.near_warn:
                continue
            same = "정답 같음" if sig(raw) == tsig else "정답 다름"
            line = "행%d %.2f [%s] '%s' ↔ 시험 '%s'" % (i, sc, same, user, tt)
            if sc >= a.near_fail:
                bad("9 시험 유사 문장", line)
            else:
                near_warn.append(line)
    # 주제어 단위로 후보 집합이 둘 이상이면 경고(실패는 아님)
    warn = {k: v for k, v in sets_by_msg.items() if len(v) > 1}

    print("신규 %d건; 유형: %s" % (len(new), dict(kinds)))
    for k in sorted(fails):
        print("[실패] %s: %d건" % (k, len(fails[k])))
        for m in fails[k][:5]: print("   -", m)
    for k, v in warn.items():
        print("[경고] 메시지 첫 구절 '%s' 의 후보 집합이 %d종: %s" % (k, len(v), sorted(v)))
    for line in near_warn:
        print("[경고] 시험과 비슷한 문장:", line)
    print("결과:", "통과" if not fails else "실패 %d항목" % len(fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
