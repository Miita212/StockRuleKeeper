"""fixed-4 학습 데이터 생성 (2026-11-09, yappang).  8B·4B 공용 최종본.

기준 = Q4B fixed-3 (우리 수정 규칙·label 키 적용 완료) + haechan data_v6 반영.
  1) v6와 되묻기 유형(reason)이 반대인 문장은 v6 정답으로 교체한다 (팀 결정 B4 저점 반등, B6 연속 배당, '규모' 큰/작은 = 지표 14·19 등).
  2) v6에만 있는 문장은 추가한다. 단 data_fixes.py 가 '의미 반전/깨진 문장'으로 제외하는 것은 뺀다. 수정 대상은 고쳐서 넣는다. 후보 키 name -> label.
  3) val = v6 val 에 같은 규칙(data_fixes, label 키)을 적용. 우리 val 에만 있던 문장은 train 으로 옮긴다(어느 쪽과도 겹치지 않을 때).
사용 (members/yappang 에서):  python3 -I -X utf8 data/scripts/build_v4_data.py --v6 ../zips/data_v6-haechan/data_v6
결과: train_model_q4b/data/{train,val}_fixed4.jsonl, {train,val}_meta_fixed4.jsonl, data/train_data/v4_*.csv, v4_report.json
"""
import argparse, collections, copy, csv, hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_fixes as DF  # noqa: E402

D = ROOT / "train_model_q4b" / "data"  # 출력(fixed-4)이 놓이는 곳
PREV = D / "backup" / "2026-11-09"  # 입력(fixed-3, 평가 문장): 2026-11-09에 백업 폴더로 옮겼다
REP = ROOT / "data" / "train_data"


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def fu(r):
    return r["messages"][1]["content"].strip()


def kind(a):
    try:
        d = json.loads(a)
    except ValueError:
        return "text"
    if not isinstance(d, dict):
        return "text"
    if d.get("needs_clarification"):
        return "clar:" + str(d.get("reason"))
    return "refuse" if d.get("refusal") else "extract"


def second(r):  # 첫 assistant 응답
    return r["messages"][2]["content"] if len(r["messages"]) > 2 else ""


def to_label(r):
    r = copy.deepcopy(r)
    for m in r["messages"]:
        if m["role"] == "assistant" and m["content"].startswith("{"):
            try:
                j = json.loads(m["content"])
            except ValueError:
                continue
            ch = False
            for c in j.get("candidates") or []:
                if "name" in c and "label" not in c:
                    c["label"] = c.pop("name")
                    ch = True
            if ch:
                m["content"] = json.dumps(j, ensure_ascii=False)
    return r


def fix_and_label(r, meta):
    nr, act, note = DF.fix_row(r, meta["type"])
    if act == "drop":
        return None, "drop", note
    meta = dict(meta)
    if act == "fix":
        meta["_fix"] = note
    return (to_label(nr), meta), act, note


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v6", required=True)
    a = ap.parse_args()
    V6 = Path(a.v6)
    t3, m3, v3, vm3 = (load(PREV / n) for n in ("train_fixed3.jsonl", "train_meta_fixed3.jsonl", "val_fixed3.jsonl", "val_meta_fixed3.jsonl"))
    t6, m6, v6, vm6 = (load(V6 / n) for n in ("train.jsonl", "train_meta.jsonl", "val.jsonl", "val_meta.jsonl"))
    v6t = collections.defaultdict(list)
    for r, m in zip(t6, m6):
        v6t[fu(r)].append((r, m))
    q3t = {fu(r) for r in t3}

    # 1) 유형 상이 -> v6 로 교체
    swap = {}
    for r in t3:
        t = fu(r)
        if t in v6t and len(r["messages"]) > 2:
            k3, k6 = kind(second(r)), kind(second(v6t[t][0][0]))
            if k3.startswith("clar") and k6.startswith("clar") and k3 != k6:
                swap[t] = v6t[t]
    out_t, out_m, log = [], [], []
    done = set()
    for r, m in zip(t3, m3):
        t = fu(r)
        if t in swap:
            if t in done:
                continue
            done.add(t)
            for r6, mm in swap[t]:
                res, act, note = fix_and_label(r6, mm)
                if res is None:
                    continue
                res[1]["_v4"] = "v6_replace"
                out_t.append(res[0]); out_m.append(res[1])
            log.append(("replace", t, kind(second(r)), kind(second(swap[t][0][0]))))
        else:
            mm = dict(m); mm["_v4"] = "q3"
            out_t.append(r); out_m.append(mm)
    # 2) v6 전용 추가
    dropped = []
    for t, lst in v6t.items():
        if t in q3t:
            continue
        for r6, mm in lst:
            res, act, note = fix_and_label(r6, mm)
            if res is None:
                dropped.append((t, note)); continue
            res[1]["_v4"] = "v6_add"
            out_t.append(res[0]); out_m.append(res[1])
            log.append(("add" if act is None else "add_fixed", t, "", kind(second(res[0]))))
    # 3) val = v6 val (+규칙), q3 val 에만 있는 문장은 train 으로
    train_texts = {fu(r) for r in out_t}
    val, valm = [], []
    for r, m in zip(v6 if False else v6, vm6):
        res, act, note = fix_and_label(r, m)
        if res is None:
            dropped.append(("[val] " + fu(r), note)); continue
        val.append(res[0]); valm.append(res[1])
    val_texts = {fu(r) for r in val}
    moved = 0
    for r, m in zip(v3, vm3):
        t = fu(r)
        if t in val_texts or t in train_texts:
            continue
        mm = dict(m); mm["_v4"] = "q3_val_moved"
        out_t.append(r); out_m.append(mm); train_texts.add(t); moved += 1
        log.append(("move_val_to_train", t, "", kind(second(r))))
    # 검증
    ev = {json.loads(l)["text"].strip() for l in open(D / "test_set.jsonl", encoding="utf-8") if l.strip()}
    assert not (train_texts & ev) and not ({fu(r) for r in val} & ev), "평가 문장이 섞임"
    assert not (train_texts & {fu(r) for r in val}), "train/val 겹침"
    assert len(out_t) == len(out_m) and len(val) == len(valm)

    write(D / "train_fixed4.jsonl", out_t); write(D / "train_meta_fixed4.jsonl", out_m)
    write(D / "val_fixed4.jsonl", val); write(D / "val_meta_fixed4.jsonl", valm)
    REP.mkdir(parents=True, exist_ok=True)
    with open(REP / "v4_changes.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["조치", "입력 문장", "기존(q3) 응답", "반영 후 응답"]); w.writerows(log)
    with open(REP / "v4_dropped.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["제외한 문장", "사유"]); w.writerows(dropped)
    kc = collections.Counter(kind(x["content"]) for r in out_t for x in r["messages"] if x["role"] == "assistant")
    rep = {"train": len(out_t), "val": len(val), "replaced": len(swap), "added": sum(1 for l in log if l[0].startswith("add")),
           "dropped": len(dropped), "q3_val_moved_to_train": moved, "answers": dict(kc),
           "sha256": {n: sha(D / n) for n in ("train_fixed4.jsonl", "val_fixed4.jsonl", "train_meta_fixed4.jsonl", "val_meta_fixed4.jsonl")}}
    (REP / "v4_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


main()
