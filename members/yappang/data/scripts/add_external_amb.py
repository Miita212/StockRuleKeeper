"""외부 LLM이 만든 '지표 모호' 되묻기 문장(stock_ambiguous_450.jsonl)을 fixed-2 에 더해 fixed-3 을 만든다.

입력  : 외부 LLM 출력(group, text, keyword, style) + data/train_data/{train,val}_fixed2(.jsonl|_meta_fixed2.jsonl)
출력  : data/train_data/{train,val}_fixed3.jsonl, *_meta_fixed3.jsonl, v3_external_report.json, v3_external_rejected.csv
정답은 코드가 만든다: candidates = 그룹 후보의 {id, label}, message = 그룹의 개념어(build_v3_data.AMB) + 문장 틀.
LLM의 keyword 는 관형형이 많아 조사를 붙이면 깨지므로 메시지에 쓰지 않고 메타에만 남긴다.
검사: 형식, 숫자, 지표 이름·별칭, 금지 개념어, 추천류, 평가 문장·기존 학습 문장과의 겹침, 자체 중복. 걸리면 버리고 사유를 CSV 에 적는다.

실행 (members/yappang 에서)
  python -I -X utf8 data/scripts/add_external_amb.py [--src train_model_q4b/data/stock_ambiguous_450.jsonl]
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_v3_data as b  # noqa: E402  (MASTER, amb_message, to_row, FORBID, EVAL_TEXTS 를 재사용)
import data_fixes  # noqa: E402

YAPPANG = HERE.parents[1]
OUT = YAPPANG / "data" / "train_data"

# 프롬프트의 그룹 표(G1~G18)와 같은 순서: (후보 지표, 메시지에 쓸 개념어)
GROUPS = {
    "G1": ((8, 9), "성장"), "G2": ((1, 2, 4, 18), "안전하다고"), "G3": ((10, 11, 16), "싸다고"), "G4": ((10, 11), "싸다고"),
    "G5": ((12, 13), "배당"), "G6": ((5, 7), "이익"), "G7": ((5, 6, 7), "잘 번다는 건"), "G8": ((15, 19, 20), "관심이 몰린다는 건"),
    "G9": ((19, 20), "거래가 활발하다는 건"), "G10": ((16, 17), "바닥권"), "G11": ((14, 19, 20), "인기가 많다는 건"),
    "G12": ((1, 2), "대출이 많다는 건"), "G13": ((1, 2, 3), "이자 부담은"), "G14": ((10, 11, 15), "거품은"),
    "G15": ((15, 20), "급등은"), "G16": ((15, 16), "폭락은"), "G17": ((8, 14), "커진다는 건"), "G18": ((4, 5, 6), "위험하다는 건"),
}
EXTRA_NAMES = ["PER", "PBR", "시총", "거래대금", "변동성", "부채", "배당수익률", "영업이익", "순이익률", "수익률", "증가율", "성장률", "자본잠식", "차입금", "이자보상", "거래량"]
RECO = re.compile(r"추천|오를|사야|팔아야|수익 보장|얼마 벌")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(YAPPANG / "train_model_q4b" / "data" / "stock_ambiguous_450.jsonl"))
    a = ap.parse_args()

    names = set(EXTRA_NAMES)
    for m in b.MASTER.values():
        names |= {m["name"], m["ui_name"]} | set(m.get("alias", []))
    existing = {data_fixes.first_user(r) for r in read_jsonl(OUT / "train_fixed2.jsonl") + read_jsonl(OUT / "val_fixed2.jsonl")}

    src = [json.loads(l) for l in Path(a.src).read_text(encoding="utf-8").splitlines() if l.strip()]
    kept, rej, seen = [], [], set()
    for r in src:
        text = str(r.get("text", "")).strip()
        why = None
        if set(r) != {"group", "text", "keyword", "style"} or r["group"] not in GROUPS or not text:
            why = "형식/그룹 오류"
        elif re.search(r"\d", text):
            why = "숫자 포함"
        elif next((n for n in names if n and n in text), None):
            why = "지표 이름 포함: " + next(n for n in names if n and n in text)
        elif next((w for w in b.FORBID if w in text), None):
            why = "평가 개념어: " + next(w for w in b.FORBID if w in text)
        elif RECO.search(text):
            why = "추천·매매 표현"
        elif text in b.EVAL_TEXTS:
            why = "평가 문장과 같음"
        elif text in existing:
            why = "기존 학습 문장과 같음"
        elif text in seen:
            why = "자체 중복"
        if why:
            rej.append([r.get("group"), text, why])
            continue
        seen.add(text)
        kept.append(r)

    train, tmeta = read_jsonl(OUT / "train_fixed2.jsonl"), read_jsonl(OUT / "train_meta_fixed2.jsonl")
    val, vmeta = read_jsonl(OUT / "val_fixed2.jsonl"), read_jsonl(OUT / "val_meta_fixed2.jsonl")
    n_tr = n_va = 0
    for k, r in enumerate(kept):
        group, kw = GROUPS[r["group"]]
        msg = b.amb_message(group, kw)
        ans = json.dumps({"needs_clarification": True, "reason": "AMBIGUOUS_INDICATOR", "message": msg,
                          "candidates": [{"id": i, "label": b.MASTER[i]["name"]} for i in group]}, ensure_ascii=False)
        row = b.to_row(r["text"].strip(), ans)
        meta = {"type": "S2", "indicator_ids": list(group), "style": r["style"], "kind": "되묻기(지표 모호)",
                "group": r["group"], "keyword": r["keyword"], "_source": "external_llm:" + Path(a.src).name}
        if k % 20 == 7:
            val.append(row); vmeta.append(meta); n_va += 1
        else:
            train.append(row); tmeta.append(meta); n_tr += 1

    problems = []
    tf = {data_fixes.first_user(r) for r in train}
    vf = {data_fixes.first_user(r) for r in val}
    if tf & vf:
        problems.append(f"train/val 겹침 {len(tf & vf)}건")
    if (tf | vf) & b.EVAL_TEXTS:
        problems.append("평가 문장 섞임")
    if len(train) != len(tmeta) or len(val) != len(vmeta):
        problems.append("대화·메타 줄 수 불일치")

    report = {"입력": str(a.src), "입력 sha256": sha(a.src), "입력 줄 수": len(src), "반영": len(kept), "버림": len(rej),
              "버린 사유": dict(Counter(x[2].split(":")[0] for x in rej)), "추가": {"train": n_tr, "val": n_va},
              "그룹별 반영": dict(Counter(r["group"] for r in kept)), "결과": {}, "검사 문제": problems}
    for nm, rows, metas in (("train", train, tmeta), ("val", val, vmeta)):
        for fname, data in ((f"{nm}_fixed3.jsonl", rows), (f"{nm}_meta_fixed3.jsonl", metas)):
            with open(OUT / fname, "w", encoding="utf-8", newline="\n") as f:
                for x in data:
                    f.write(json.dumps(x, ensure_ascii=False) + "\n")
            report["결과"][fname] = {"lines": len(data), "sha256": sha(OUT / fname)}
    (OUT / "v3_external_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(OUT / "v3_external_rejected.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["그룹", "문장", "사유"])
        w.writerows(rej)
    print(json.dumps({k: report[k] for k in ("입력 줄 수", "반영", "버림", "버린 사유", "추가", "검사 문제")}, ensure_ascii=False, indent=1))
    print("학습", len(train), "검증", len(val))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
