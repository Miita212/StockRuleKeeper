"""Ollama 에 등록된 모델을 평가 111문항으로 채점한다 (8B 팀 모델·Q4B GGUF 공용).

호출 방식은 백엔드 llm/provider.py `_local` 과 같다: /api/chat, think=false, format=json, temperature 0.
지표 정의는 eval_q4b.py 를 그대로 가져다 쓰고(필드 정확도 = source=user 지표의 id·operator·value·unit 전부 일치),
8B 쪽과 비교할 수 있게 haechan 식 "필드 단위 정확도"와 응답 유형 혼동표를 더 낸다.

사용 (members/yappang/train_model 에서):
  python3 -I scripts/eval_ollama.py --model qwen3-8b-stockrule-v3-2ep --tag ollama-v3-2ep
  python3 -I scripts/eval_ollama.py --model ... --tag t --limit 6        # 앞 6문항만(시험용)
결과: outputs/eval_<tag>.jsonl (다시 실행하면 이어서 하지 않고 처음부터 한다)
"""
import argparse
import collections
import importlib.util
import json
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("eval_q4b", HERE / "eval_q4b.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)  # eval_q4b 의 EVAL_FILES, field_score, report 를 재사용 (무거운 import 는 main 안에 있다)

FIELDS = ("operator", "value", "unit", "source")


def kind_of(d):
    if not isinstance(d, dict):
        return "invalid"
    if d.get("needs_clarification"):
        return "clarify"
    if d.get("refusal"):
        return "refuse"
    if "indicators" in d:
        return "extract"
    return "other"


def eq(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) < 1e-9
    return a == b


def ask(model, messages, url, num_predict):
    body = {"model": model, "messages": messages, "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0, "num_predict": num_predict}}
    req = urllib.request.Request(url + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req, timeout=900))
    return res["message"]["content"].strip(), res.get("eval_count", 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--url", default="http://localhost:11434")
    ap.add_argument("--max-new", type=int, default=900)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    rows = [json.loads(l) for p in q.EVAL_FILES for l in open(p, encoding="utf-8") if l.strip()]
    if a.limit:
        rows = rows[:a.limit]
    out = HERE.parent / "outputs" / f"eval_{a.tag}.jsonl"
    out.parent.mkdir(exist_ok=True)

    results, t0, ntok = [], time.time(), 0
    for i, r in enumerate(rows, 1):
        text, n = ask(a.model, r["messages"][:2], a.url, a.max_new)
        ntok += n
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        results.append({"eval_id": r["eval_id"], "kind": r["kind"], "text": r["text"], "expected": r["output"],
                        "generated": text, "parsed": parsed})
        if i % 10 == 0 or i == len(rows):
            print(f"{i}/{len(rows)}  {time.time() - t0:.0f}s", flush=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    q.report(results, a.tag, out)  # eval_q4b.py 와 같은 지표

    # --- 추가 지표 ---
    conf = collections.Counter((kind_of(r["expected"]), kind_of(r["parsed"])) for r in results)
    print("\n[응답 유형 혼동표] 정답 → 모델 응답")
    for g in ("extract", "clarify", "refuse"):
        row = {p: conf[(g, p)] for p in ("extract", "clarify", "refuse", "other", "invalid") if conf[(g, p)]}
        print(f"  {g:8} {sum(row.values()):3}건 → {row}")
    ok = sum(kind_of(r["expected"]) == kind_of(r["parsed"]) for r in results)
    print(f"  유형 일치 {ok}/{len(results)} = {ok / len(results):.1%}")

    fo = ft = 0   # haechan 식: 정답의 모든 지표(default 포함)에 대해 operator·value·unit·source 를 필드 단위로 비교
    for r in results:
        g, p = r["expected"], r["parsed"]
        if kind_of(g) != "extract" or kind_of(p) != "extract":
            if kind_of(g) == "extract":
                ft += len(g["indicators"]) * len(FIELDS)
            continue
        pm = {x.get("id"): x for x in p.get("indicators", []) if isinstance(x, dict)}
        for gi in g["indicators"]:
            pi = pm.get(gi["id"], {})
            for k in FIELDS:
                ft += 1
                fo += eq(gi.get(k), pi.get(k))
    print(f"[haechan 식 필드 단위 정확도, default 포함] {fo}/{ft} = {fo / ft:.1%}  (후하게 나오는 지표, 위의 '필드 정확도'와 다른 정의)")
    print(f"평균 {(time.time() - t0) / len(results):.1f}s/문항, 생성 {ntok}토큰, {ntok / (time.time() - t0):.1f} tok/s")


if __name__ == "__main__":
    main()
