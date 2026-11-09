"""학습 데이터 토큰 길이 분포. Qwen3-4B 채팅 템플릿(enable_thinking=False) 기준.
실행: python -I scripts/token_stats.py
"""
import json, statistics
from collections import defaultdict
from pathlib import Path
from transformers import AutoTokenizer

D = Path(__file__).resolve().parents[1] / "data"
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B")
for name in ["train", "val"]:
    rows = [json.loads(l) for l in open(D / f"{name}.jsonl", encoding="utf-8")]
    meta = [json.loads(l) for l in open(D / f"{name}_meta.jsonl", encoding="utf-8")]
    by = defaultdict(list)
    for r, m in zip(rows, meta):
        ids = tok.apply_chat_template(r["messages"], tokenize=True, enable_thinking=False)
        n = len(ids["input_ids"] if hasattr(ids, "keys") else ids)
        by[m["type"]].append(n)
    allv = [n for v in by.values() for n in v]
    def q(v, p): s = sorted(v); return s[min(len(s) - 1, int(len(s) * p))]
    print(f"== {name}  전체 {len(allv)}건  평균 {statistics.mean(allv):.0f}  p95 {q(allv,.95)}  p99 {q(allv,.99)}  최대 {max(allv)}")
    for t in sorted(by):
        v = by[t]; print(f"  {t:5s} {len(v):5d}건  평균 {statistics.mean(v):6.0f}  p95 {q(v,.95):5d}  최대 {max(v):5d}")
    for L in (512, 768, 1024, 1536, 2048):
        print(f"  >{L}: {sum(n > L for n in allv)}건")
