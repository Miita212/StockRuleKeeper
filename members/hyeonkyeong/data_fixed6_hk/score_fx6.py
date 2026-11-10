"""모델 출력(eval_model.py 결과 jsonl)을 두 벌의 정답으로 채점한다 (hyeonkyeong, 2026-11-10).

정답 두 벌
  - 현재: yappang test_set.jsonl 234 (11/10 24792a4에서 G1~G7 기준으로 10건 수정) + holdout_new_hk6.jsonl 30   (주 기준)
  - 수정전: --before로 준 수정 전 test_set (예: git show 2d0732d:members/yappang/train_model_q4b/data/test_set.jsonl) + 같은 holdout 30
지표
  - yappang 기준(eval_q4b.py report 정의): JSON 유효율, 형태 일치율, 필드 정확도, 은어 변환율, 완전 일치율
  - 구조 일치(docs/8B_v6_vs_fixed4_yappang채점기준_비교.md 6장): 거절 여부 / 되묻기 이유+대상 id 집합 /
    추출은 20개 지표(id·operator·value·unit)와 anchors가 같으면 맞음 (anchors가 없으면 source user·inferred id로 채움)

사용: python3 -I -X utf8 score_fx6.py <이름>=<출력.jsonl> ... [--before 수정전_test_set.jsonl] [--out 결과.json]
"""
import argparse
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEST_SET = HERE.parent.parent / "yappang" / "train_model_q4b" / "data" / "test_set.jsonl"
SLANG_WORDS = ("별칭", "오타", "구어")  # eval_q4b.py와 같음
CHANGED = ["T031", "T064", "T065", "T106", "T107", "T193", "T194", "T197", "T228", "T229"]  # 11/10 수정된 10문항


def read(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def parse(s):
    try:
        return json.loads(s.strip())
    except (json.JSONDecodeError, AttributeError):
        return None


def user_fields(obj):  # eval_q4b.py와 같음
    out = {}
    if isinstance(obj, dict) and isinstance(obj.get("indicators"), list):
        for x in obj["indicators"]:
            if isinstance(x, dict) and x.get("source") == "user":
                out[x.get("id")] = (x.get("operator"), x.get("value"), x.get("unit"))
    return out


def kind_of(o):
    if not isinstance(o, dict):
        return "invalid"
    if o.get("refusal"):
        return "refuse"
    if o.get("needs_clarification"):
        return "clarify"
    if "indicators" in o:
        return "extract"
    return "other"


def clar_key(o):
    ids = sorted(c.get("id") for c in o.get("candidates") or [] if isinstance(c, dict) and "id" in c)
    if not ids and o.get("indicator_id") is not None:
        ids = [o["indicator_id"]]
    return o.get("reason"), tuple(ids)


def ext_key(o):
    ind = tuple(sorted((x.get("id"), x.get("operator"), x.get("value"), x.get("unit"))
                       for x in o.get("indicators") or [] if isinstance(x, dict)))
    anchors = o.get("anchors")
    if anchors is None:
        anchors = [x.get("id") for x in o.get("indicators") or [] if isinstance(x, dict) and x.get("source") in ("user", "inferred")]
    return ind, tuple(sorted(anchors))


def struct_ok(gold, pred):
    g, p = kind_of(gold), kind_of(pred)
    if g != p:
        return False
    if g == "refuse":
        return True
    if g == "clarify":
        return clar_key(gold) == clar_key(pred)
    if g == "extract":
        return ext_key(gold) == ext_key(pred)
    return False


def score(rows, preds):
    """rows: 정답 행(test 형식), preds: 같은 순서의 모델 출력 dict(parsed)"""
    n = len(rows)
    valid = sum(p is not None for p in preds)
    shape = sum(isinstance(p, dict) and set(p) == set(r["output"]) for r, p in zip(rows, preds))
    exact = sum(p is not None and p == r["output"] for r, p in zip(rows, preds))
    fo = ft = 0
    for r, p in zip(rows, preds):
        g, q = user_fields(r["output"]), user_fields(p)
        fo += sum(1 for k, v in g.items() if q.get(k) == v)
        ft += len(g)
    slang = [(r, p) for r, p in zip(rows, preds) if any(w in r["kind"] for w in SLANG_WORDS)]
    slang_ok = sum(p is not None and p == r["output"] for r, p in slang)
    st = collections.defaultdict(lambda: [0, 0])
    for r, p in zip(rows, preds):
        ok = struct_ok(r["output"], p)
        for key in ("전체", kind_of(r["output"]), r["source"]):
            st[key][0] += ok
            st[key][1] += 1
    return {
        "n": n,
        "yappang": {"JSON 유효율": [valid, n], "형태 일치율": [shape, n], "필드 정확도": [fo, ft],
                    "은어 변환율": [slang_ok, len(slang)], "완전 일치율": [exact, n]},
        "구조 일치": {k: v for k, v in st.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("preds", nargs="+", help="이름=eval_model.py 출력 jsonl")
    ap.add_argument("--before", default=None, help="수정 전 test_set.jsonl (주면 수정전 정답으로도 채점)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    holdout = read(HERE / "holdout_new_hk6.jsonl")
    original = read(TEST_SET) + holdout
    golds = [("현재", original)]
    if a.before:
        before = read(a.before) + holdout
        assert [r["text"] for r in before] == [r["text"] for r in original], "두 정답 세트의 입력 순서가 다르다"
        golds.append(("수정전", before))

    result = {}
    for spec in a.preds:
        name, path = spec.split("=", 1)
        out = read(path)
        assert len(out) == len(original), f"{name}: {len(out)}건 (264건이어야 함)"
        assert [o["text"] for o in out] == [r["text"] for r in original], f"{name}: 입력 순서가 다르다"
        preds = [parse(o["raw"]) for o in out]
        res = {}
        for gname, gold in golds:
            for part, sel in (("전체264", lambda r: True), ("기존234", lambda r: r["source"] != "holdout_hk"),
                              ("새시험30", lambda r: r["source"] == "holdout_hk")):
                idx = [i for i, r in enumerate(gold) if sel(r)]
                res[f"{gname}/{part}"] = score([gold[i] for i in idx], [preds[i] for i in idx])
        # 기준이 바뀐 9문항: 문항별 모델 답 구조
        changed = {}
        for i, r in enumerate(original):
            if r["test_id"] in CHANGED:
                p = preds[i]
                k = kind_of(p)
                desc = k if k in ("refuse", "invalid", "other") else (
                    f"{clar_key(p)[0]} {list(clar_key(p)[1])}" if k == "clarify" else f"extract anchors={list(ext_key(p)[1])}")
                changed[r["test_id"]] = {"text": r["text"], "pred": desc,
                                         **{f"{g} 정답과 구조 일치": struct_ok(gs[i]["output"], p) for g, gs in golds}}
        res["기준 바뀐 9문항"] = changed
        # 구조 오답 목록(원본 정답 기준)
        res["구조 오답(현재)"] = [{"test_id": r["test_id"], "source": r["source"], "kind": r["kind"], "text": r["text"],
                                "gold": kind_of(r["output"]), "pred": kind_of(preds[i]), "raw": out[i]["raw"][:300]}
                               for i, r in enumerate(original) if not struct_ok(r["output"], preds[i])]
        result[name] = res

    def pct(v):
        return f"{v[0] / max(v[1], 1) * 100:.1f}% ({v[0]}/{v[1]})"

    for gname, _ in golds:
        print(f"\n## 정답 {gname}")
        for part in ("전체264", "기존234", "새시험30"):
            print(f"\n### {part}")
            keys = ["전체", "extract", "clarify", "refuse"]
            print("| 모델 | 구조 " + " | 구조 ".join(keys) + " | 완전 일치 | 필드 정확도 | 형태 일치 |")
            for name, res in result.items():
                s = res[f"{gname}/{part}"]
                cells = [pct(s["구조 일치"].get(k, [0, 0])) for k in keys]
                y = s["yappang"]
                print(f"| {name} | " + " | ".join(cells) + f" | {pct(y['완전 일치율'])} | {pct(y['필드 정확도'])} | {pct(y['형태 일치율'])} |")
    print("\n## 출처별 구조 일치 (현재 정답)")
    srcs = ["official111", "haechan58", "haechan31", "haechan34", "holdout_hk"]
    print("| 모델 | " + " | ".join(srcs) + " |")
    for name, res in result.items():
        s = res["현재/전체264"]["구조 일치"]
        print(f"| {name} | " + " | ".join(pct(s.get(k, [0, 0])) for k in srcs) + " |")
    if a.out:
        json.dump(result, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
