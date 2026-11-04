"""V-1 자동 검증 코드: 생성된 학습 데이터(jsonl)를 규칙 V1~V10으로 거른다.

사용법
    python validate_data.py --master-dir <마스터 JSON 폴더> --input a.jsonl b.jsonl \
        [--eval eval_*.jsonl] [--out-pass pass.jsonl] [--out-fail fail.jsonl]

마스터 폴더에는 지표 마스터(H1-a/b/c) JSON 파일이 들어 있어야 한다(파일 이름에 'indicator_master'가
들어간 *.json 전부 읽는다). 마스터 양식은 byungjun의 H1-0 문서를 따른다.

샘플 형식(한 줄 = 한 샘플)
    {"type": "S1", "messages": [{"role": "...", "content": "..."}, ...], "indicator_ids": [1],
     "locked": [6], "seed_id": "..."}
  또는 {"type": "S1", "input": "말", "output": {...}} 도 받는다(내부에서 messages로 바꿈).
  type: S1~S5는 JSON 정답이 있어야 하고(S5 거절은 일반 문장도 허용), S6~S8은 설명 문장이다.
  locked / seed_id / indicator_ids 는 선택 필드다.

규칙(검증규칙 시트)
    V1 JSON 형식 / V2 지표 id 1~20 / V3 값 범위 / V4 부등호·단위 / V5 잠긴 지표 / V6 중복·충돌
    V7 금지 표현 / V8 리포트 숫자 일치 / V9 평가 세트 격리 / V10 마스터에 없는 사실

주의: 팀 합의 전 규칙이 많다(기본값, '이내' 해석, 정답 JSON 모양 등). 그 부분은 아래 상수에 모아 두었다.
"""

import argparse
import json
import re
import sys
from pathlib import Path

JSON_REQUIRED_TYPES = {"S1", "S2", "S3", "S4"}
TEXT_TYPES = {"S6", "S7", "S8"}
CLARIFY_REASONS = {"VALUE_MISSING", "AMBIGUOUS_INDICATOR", "PERIOD_MISSING"}
OPTION_COUNT = 3  # H3-0: 선택지는 항상 3개
SOURCES = {"user", "default"}

# V7: 추천·단정·예측 표현 (H6 가이드가 나오면 여기를 맞춘다). 부정형("추천하지 않아요")은 걸리지 않게 썼다.
FORBIDDEN_PATTERNS = [
    r"사세요", r"파세요", r"매수하세요", r"매도하세요", r"매수를 권", r"매도를 권",
    r"사는 ?게 좋", r"사야 (해|합|돼|됩)", r"팔아야",
    r"추천드", r"추천해 ?드", r"추천할게", r"추천합니다",
    r"반드시 (오|상승|수익|성공)", r"무조건", r"틀림없이", r"확실(히|하게) (오|상승|수익)",
    r"오를 (거|것|겁)", r"떨어질 (거|것|겁)", r"수익을? ?보장", r"손실 ?없",
]
AVERAGE_CLAIM = re.compile(r"(업종|업계|시장|코스피|산업)\s*평균[^.!?\n]{0,12}?-?\d")
NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


# ---------------------------------------------------------------- 마스터
def load_master(master_dir):
    """마스터 JSON들을 읽어 {id: 행} 으로 돌려준다."""
    master = {}
    files = sorted(Path(master_dir).glob("*indicator_master*.json"))
    if not files:
        raise FileNotFoundError(f"마스터 JSON을 찾지 못했어요: {master_dir}")
    for f in files:
        for row in json.loads(f.read_text(encoding="utf-8")):
            master[int(row["id"])] = row
    if sorted(master) != list(range(1, 21)):
        missing = sorted(set(range(1, 21)) - set(master))
        print(f"[경고] 마스터에 지표 {missing} 가 없어요", file=sys.stderr)
    return master


# ---------------------------------------------------------------- 도우미
def norm(text):
    """중복·격리 비교용: 공백·기호를 지우고 소문자로."""
    return re.sub(r"[^0-9a-z가-힣]", "", str(text).lower())


def numbers_in(text):
    out = set()
    for m in NUM.findall(str(text)):
        try:
            out.add(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def numeric_leaves(obj):
    """JSON 안의 모든 숫자(문자열 속 숫자 포함)."""
    out = set()
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        out |= numbers_in(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out |= numeric_leaves(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= numeric_leaves(v)
    return out


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def parse_json_dict(text):
    try:
        obj = json.loads(text)
    except (TypeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def normalize_record(rec):
    """input/output 형식을 messages 형식으로 맞춘다."""
    if "messages" in rec:
        return rec
    if "input" in rec and "output" in rec:
        out = rec["output"]
        content = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        new = dict(rec)
        new["messages"] = [
            {"role": "user", "content": rec["input"]},
            {"role": "assistant", "content": content},
        ]
        return new
    return rec


# ---------------------------------------------------------------- 규칙 검사 (각각 [(규칙, 메시지)] 반환)
def check_indicator_entry(entry, master, where):
    """지표 한 개(id/operator/value/unit)에 대한 V2·V3·V4."""
    errs = []
    iid = entry.get("id")
    if not (isinstance(iid, int) and not isinstance(iid, bool)) or iid not in master:
        return [("V2", f"{where}: 지표 id {iid!r} 는 1~20 안에 없어요")]
    m = master[iid]
    if "operator" in entry:
        allowed = set(m.get("allowed_operators") or []) | {m["operator"]}
        if entry["operator"] not in allowed:
            errs.append(("V4", f"{where}: id {iid} 부등호 {entry['operator']!r} 허용 안 됨 {sorted(allowed)}"))
    if "unit" in entry and entry["unit"] != m["unit"]:
        errs.append(("V4", f"{where}: id {iid} 단위 {entry['unit']!r} 가 마스터 {m['unit']!r} 와 달라요"))
    if "value" in entry:
        v = entry["value"]
        if not is_num(v):
            errs.append(("V3", f"{where}: id {iid} 값 {v!r} 가 숫자가 아니에요"))
        elif not (m["min"] <= v <= m["max"]):
            errs.append(("V3", f"{where}: id {iid} 값 {v} 가 범위 {m['min']}~{m['max']} 를 벗어나요"))
    return errs


def check_output_obj(obj, master, locked):
    """정답 JSON 한 개의 모양(V1)과 안의 지표(V2~V5)."""
    errs = []

    def need(cond, msg):
        if not cond:
            errs.append(("V1", msg))
        return cond

    if obj.get("needs_clarification") is True:
        need(isinstance(obj.get("message"), str) and obj["message"].strip(), "되묻기에 message 가 없어요")
        reason = obj.get("reason")
        need(reason in CLARIFY_REASONS, f"되묻기 reason {reason!r} 는 {sorted(CLARIFY_REASONS)} 중 하나여야 해요")
        if reason == "VALUE_MISSING":
            iid = obj.get("indicator_id")
            ok = need("options" in obj, "VALUE_MISSING 되묻기에 options 가 없어요")
            if ok and need(isinstance(obj["options"], list) and len(obj["options"]) == OPTION_COUNT,
                           f"선택지는 {OPTION_COUNT}개여야 해요"):
                for opt in obj["options"]:
                    if need(isinstance(opt, dict) and "label" in opt and "value" in opt,
                            "선택지에 label/value 가 없어요"):
                        errs += check_indicator_entry({"id": iid, "value": opt["value"]}, master, "선택지")
        elif reason == "AMBIGUOUS_INDICATOR":
            cand = obj.get("candidates")
            if need(isinstance(cand, list) and cand, "AMBIGUOUS_INDICATOR 되묻기에 candidates 가 없어요"):
                for c in cand:
                    cid = c.get("id") if isinstance(c, dict) else c
                    errs += check_indicator_entry({"id": cid}, master, "후보")
    elif obj.get("refusal") is True:
        need(isinstance(obj.get("message"), str) and obj["message"].strip(), "거절에 message 가 없어요")
        need(obj.get("indicators", []) == [], "거절인데 indicators 가 비어 있지 않아요")
    elif "changes" in obj:
        if need(isinstance(obj["changes"], list) and obj["changes"], "changes 가 비어 있어요"):
            for ch in obj["changes"]:
                if not need(isinstance(ch, dict) and "id" in ch and "before" in ch and "after" in ch,
                            "changes 항목에 id/before/after 가 없어요"):
                    continue
                errs += check_indicator_entry({"id": ch["id"], "value": ch["after"], "unit": ch.get("unit")}
                                              if "unit" in ch else {"id": ch["id"], "value": ch["after"]},
                                              master, "changes")
                if ch["id"] in locked:  # V5
                    errs.append(("V5", f"잠긴 지표 {ch['id']} 를 바꿨어요"))
        for sid in obj.get("skipped_locked", []):
            if sid not in locked:
                errs.append(("V5", f"skipped_locked 의 {sid} 는 잠긴 지표가 아니에요"))
    elif "indicators" in obj:
        inds = obj["indicators"]
        if need(isinstance(inds, list) and inds, "indicators 가 비어 있어요"):
            seen = set()
            for e in inds:
                if not need(isinstance(e, dict) and "id" in e and "operator" in e and "value" in e and "unit" in e,
                            "indicators 항목에 id/operator/value/unit 이 없어요"):
                    continue
                if e["id"] in seen:
                    errs.append(("V1", f"지표 {e['id']} 가 두 번 나와요"))
                seen.add(e["id"])
                if "source" in e and e["source"] not in SOURCES:
                    errs.append(("V1", f"source {e['source']!r} 는 user/default 여야 해요"))
                errs += check_indicator_entry(e, master, "indicators")
            for a in obj.get("anchors", []):
                errs += check_indicator_entry({"id": a}, master, "anchors")
                if a not in seen:
                    errs.append(("V1", f"anchors 의 {a} 가 indicators 에 없어요"))
    else:
        errs.append(("V1", "알 수 없는 정답 모양이에요 (indicators/changes/needs_clarification/refusal 중 하나여야 해요)"))
    return errs


def check_text(text):
    """V7: 금지 표현."""
    return [("V7", f"금지 표현 {m.group(0)!r}")
            for p in FORBIDDEN_PATTERNS for m in [re.search(p, text)] if m]


def check_master_facts(text, rec, master, prior_numbers):
    """V10: 마스터에 없는 사실·수치."""
    errs = []
    blob = " ".join(str(v) for m in master.values()
                    for v in (m.get("definition", ""), m.get("note", ""), " ".join(m.get("source", []))))
    for m in AVERAGE_CLAIM.finditer(text):
        if m.group(0) not in blob:
            errs.append(("V10", f"출처 없는 평균 수치 주장: {m.group(0)!r}"))
    allowed = set(prior_numbers)
    for iid in rec.get("indicator_ids", []):
        if iid in master:
            m = master[iid]
            allowed |= {float(m["default"]), float(m["min"]), float(m["max"])}
            allowed |= numbers_in(m.get("definition", ""))
    stray = sorted(n for n in claim_numbers(text) if n not in allowed)
    if stray:
        errs.append(("V10", f"입력·마스터에 없는 숫자 {stray}"))
    return errs


GENERIC_UNITS = {"년", "개월", "개", "번", "일", "주", "위", ""}
NUM_UNIT = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)\s*(%|퍼센트|배|년|개월|천억|백억|억|조|원|개|번|일|주|위)?")
# H1-0 규칙 3: 금액은 억원 숫자로 통일 (1조원 = 10000)
EOK_FACTOR = {"조": 10000, "천억": 1000, "백억": 100}


def claim_numbers(text):
    """'1년에 버는 돈', '한 번' 같은 일반 표현의 1은 사실 주장이 아니라서 뺀다."""
    out = set()
    for num, unit in NUM_UNIT.findall(str(text)):
        try:
            n = float(num.replace(",", ""))
        except ValueError:
            continue
        if n == 1 and (unit or "") in GENERIC_UNITS:
            continue
        if unit in EOK_FACTOR:  # 마스터는 억원 숫자라서 환산한 값으로 비교한다
            n *= EOK_FACTOR[unit]
        out.add(n)
    return out


def check_report(user_text, answer):
    """V8: 리포트 문장의 숫자가 입력 JSON의 숫자와 같은지."""
    m = re.search(r"\{.*\}", user_text, re.S)
    inp = parse_json_dict(m.group(0)) if m else None
    if inp is None:
        return [("V8", "S8 입력에서 JSON 을 찾지 못했어요")]
    allowed = numeric_leaves(inp)
    stray = sorted(n for n in numbers_in(answer) if n not in allowed)
    if stray:
        return [("V8", f"문장의 숫자 {stray} 가 입력에 없어요")]
    return []


def validate_record(rec, master):
    """샘플 하나의 V1~V5, V7, V8, V10. 실패 목록을 돌려준다."""
    rec = normalize_record(rec)
    errs = []
    msgs = rec.get("messages")
    if not (isinstance(msgs, list) and msgs and all(
            isinstance(m, dict) and m.get("role") in {"system", "user", "assistant"}
            and isinstance(m.get("content"), str) and m["content"].strip() for m in msgs)):
        return [("V1", "messages 형식이 틀렸어요")]
    if msgs[-1]["role"] != "assistant":
        return [("V1", "마지막 메시지가 assistant 가 아니에요")]
    typ = rec.get("type")
    locked = set(rec.get("locked", []))
    assistants = [m["content"] for m in msgs if m["role"] == "assistant"]
    saw_json = False
    for i, content in enumerate(assistants):
        obj = parse_json_dict(content)
        if obj is not None:
            saw_json = True
            errs += check_output_obj(obj, master, locked)
        else:
            errs += check_text(content)
    if typ in JSON_REQUIRED_TYPES and not saw_json:
        errs.append(("V1", f"{typ} 샘플인데 JSON 정답이 없어요"))
    if typ == "S5" and not saw_json:
        pass  # 거절 문장은 일반 문장도 허용
    final = msgs[-1]["content"]
    if parse_json_dict(final) is None:
        if typ == "S8":
            user = next((m["content"] for m in msgs if m["role"] == "user"), "")
            errs += check_report(user, final)
        if typ in {"S3", "S6", "S7"}:
            prior = set()
            for m in msgs[:-1]:
                prior |= numbers_in(m["content"])
            errs += check_master_facts(final, rec, master, prior)
    # 같은 규칙·같은 메시지는 한 번만
    seen, uniq = set(), []
    for e in errs:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq


def user_key(rec):
    rec = normalize_record(rec)
    users = [m["content"] for m in rec.get("messages", []) if isinstance(m, dict) and m.get("role") == "user"]
    return norm(" ".join(users)) if users else None


def answer_key(rec):
    rec = normalize_record(rec)
    msgs = rec.get("messages", [])
    return norm(msgs[-1]["content"]) if msgs and isinstance(msgs[-1], dict) else None


def check_duplicates(records):
    """V6: 같은 질문+같은 답은 두 번째부터 중복, 같은 질문+다른 답은 충돌(둘 다 아닌 뒤의 것)로 본다."""
    seen = {}
    result = {}
    for idx, rec in enumerate(records):
        k = (rec.get("type"), user_key(rec))
        if k[1] is None:
            continue
        a = answer_key(rec)
        if k in seen:
            first_idx, first_a = seen[k]
            if a == first_a:
                kind = "중복"
            elif rec.get("type") in TEXT_TYPES:
                continue  # 설명 문장(S6~S8)은 같은 입력에 여러 문장이 정답일 수 있어 충돌로 보지 않는다
            else:
                kind = "충돌(같은 질문에 다른 정답)"
            result.setdefault(idx, []).append(("V6", f"{kind}: {first_idx + 1}번째 줄과 같은 질문"))
        else:
            seen[k] = (idx, a)
    return result


def check_eval_isolation(records, eval_records):
    """V9: 평가 세트의 질문(또는 seed_id)이 학습 데이터에 있으면 안 된다."""
    eval_keys = {user_key(r) for r in eval_records if user_key(r)}
    eval_seeds = {r["seed_id"] for r in eval_records if r.get("seed_id")}
    result = {}
    for idx, rec in enumerate(records):
        if user_key(rec) in eval_keys:
            result.setdefault(idx, []).append(("V9", "평가 세트와 같은 질문이 학습 데이터에 있어요"))
        elif rec.get("seed_id") and rec["seed_id"] in eval_seeds:
            result.setdefault(idx, []).append(("V9", f"평가 세트와 같은 seed_id {rec['seed_id']!r}"))
    return result


# ---------------------------------------------------------------- 실행
def read_jsonl(path):
    rows = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            rows.append({"_parse_error": f"{path} {n}번째 줄이 JSON 이 아니에요"})
    return rows


def validate_all(records, master, eval_records=()):
    """records → [(record, [(규칙, 메시지)...]), ...]"""
    dup = check_duplicates([r for r in records])
    leak = check_eval_isolation(records, list(eval_records)) if eval_records else {}
    out = []
    for idx, rec in enumerate(records):
        if "_parse_error" in rec:
            errs = [("V1", rec["_parse_error"])]
        else:
            errs = validate_record(rec, master)
            errs += dup.get(idx, []) + leak.get(idx, [])
        out.append((rec, errs))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="학습 데이터 자동 검증 (V1~V10)")
    ap.add_argument("--master-dir", required=True)
    ap.add_argument("--input", nargs="+", required=True)
    ap.add_argument("--eval", nargs="*", default=[])
    ap.add_argument("--out-pass")
    ap.add_argument("--out-fail")
    args = ap.parse_args(argv)

    master = load_master(args.master_dir)
    records = [r for p in args.input for r in read_jsonl(p)]
    eval_records = [r for p in args.eval for r in read_jsonl(p)]
    results = validate_all(records, master, eval_records)

    passed = [r for r, e in results if not e]
    failed = [(r, e) for r, e in results if e]
    by_rule = {}
    for _, e in failed:
        for rule in {x[0] for x in e}:
            by_rule[rule] = by_rule.get(rule, 0) + 1
    print(f"전체 {len(results)}  통과 {len(passed)}  실패 {len(failed)}")
    for rule in sorted(by_rule, key=lambda s: int(s[1:])):
        print(f"  {rule}: {by_rule[rule]}건")
    for r, e in failed[:10]:
        print("  예)", e[0][0], e[0][1])
    if args.out_pass:
        Path(args.out_pass).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in passed), encoding="utf-8")
    if args.out_fail:
        Path(args.out_fail).write_text(
            "".join(json.dumps({"record": r, "errors": e}, ensure_ascii=False) + "\n" for r, e in failed),
            encoding="utf-8")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
