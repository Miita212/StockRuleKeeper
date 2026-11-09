"""test_set.jsonl 정답 수정 (2026-11-10, yappang). fixed-6-hk 표현 기준(G1~G7) 합의 반영.
hyeonkyeong 제안본 test.jsonl(9건) + T194(가격 대비 = G4, 제안에서 빠진 1건)를 적용한다.
후보 키(label/name)는 문항 원래 형식을 유지한다. 수정 전 파일은 backup/2026-11-10/test_set_before_g1g7.jsonl.
사용 (members/yappang 에서): python3 -I -X utf8 data/scripts/apply_test_fixes_20261110.py <hk test.jsonl>
"""
import json, shutil, sys, copy
from pathlib import Path
D = Path(__file__).resolve().parents[2] / "train_model_q4b" / "data"
FIX = ["T031", "T064", "T065", "T106", "T107", "T193", "T197", "T228", "T229"]
rows = [json.loads(l) for l in open(D / "test_set.jsonl", encoding="utf-8") if l.strip()]
hk = {r["test_id"]: r for r in map(json.loads, open(sys.argv[1], encoding="utf-8")) if r["test_id"] in FIX}
by = {r["test_id"]: r for r in rows}
bak = D / "backup" / "2026-11-10"; bak.mkdir(parents=True, exist_ok=True)
if not (bak / "test_set_before_g1g7.jsonl").exists():
    shutil.copy(D / "test_set.jsonl", bak / "test_set_before_g1g7.jsonl")

def setkey(out, key):
    if out.get("candidates"):
        out = copy.deepcopy(out)
        for c in out["candidates"]:
            n = c.pop("label", None) or c.pop("name", None)
            c[key] = n
    return out

for tid in FIX:
    old = by[tid]["output"]
    key = "label" if old.get("candidates") and "label" in old["candidates"][0] else "name"
    assert hk[tid]["text"] == by[tid]["text"]
    by[tid]["output"] = setkey(hk[tid]["output"], key)
# T194: 가격 대비 효율 = G4 → 모호[10,11] (T064 와 같은 정답)
key = "label" if "label" in by["T194"]["output"]["candidates"][0] else "name"
by["T194"]["output"] = setkey(by["T064"]["output"], key)
with open(D / "test_set.jsonl", "w", encoding="utf-8", newline="\n") as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("수정", FIX + ["T194"])
