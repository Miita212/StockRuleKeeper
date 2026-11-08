"""Ollama 모델(Q4B GGUF)을 eval_model.py 와 같은 채점기·같은 데이터로 평가한다.
사용: python3 compare_q4b/run_ollama_eval.py --model haechan-cmp-q4b --data 'glob' --out DIR
호출: /api/chat, think=false, temperature 0, 시스템+사용자 메시지만 (few-shot 없음, format 제한 없음)
측정: 건당 지연시간, 생성 토큰 수.
"""
import argparse, glob, json, sys, time, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import eval_model as em

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--data", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--name", default="q4b")
a = ap.parse_args()
rows = [r for f in sorted(glob.glob(a.data)) for r in em.read_jsonl(f)]
recs, lat, toks = [], [], []
for i, r in enumerate(rows, 1):
    body = {"model": a.model, "messages": r["messages"][:2], "stream": False, "think": False,
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 1024}}
    req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.time()
    res = json.load(urllib.request.urlopen(req, timeout=600))
    lat.append(time.time() - t0); toks.append(res.get("eval_count", 0))
    g = res["message"]["content"]
    recs.append({"id": r["id"], "kind": r["kind"], "text": r["text"], "gold": r["output"], "raw": g, "score": em.score(r["output"], em.parse(g))})
    if i % 20 == 0: print(f"  {i}/{len(rows)}", flush=True)
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
(out / f"{a.name}.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in recs) + "\n", encoding="utf-8")
s = em.summarize(recs)
s["평균 지연(초/건)"] = round(sum(lat) / len(lat), 2); s["평균 생성 토큰"] = round(sum(toks) / len(toks), 1)
(out / "summary.json").write_text(json.dumps({a.name: s}, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(s, ensure_ascii=False, indent=1))
