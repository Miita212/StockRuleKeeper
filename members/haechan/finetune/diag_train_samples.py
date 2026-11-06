"""진단: 학습에 쓴 문장을 어댑터에 직접 넣어 본다 (진단 1) + 학습/평가 프롬프트 토큰 대조·첫 토큰 확률 (진단 2).

사용: python -X utf8 diag_train_samples.py --adapter runs/qwen3-8b-v2-1ep/checkpoint-153 --n 20
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

from eval_model import kind_of, parse, read_jsonl

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--train", default=str(HERE / "data_v2" / "train.jsonl"))
    ap.add_argument("--n", type=int, default=20, help="유형별 샘플 수")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(args.model)
    tok.padding_side = "left"

    # 학습 데이터에서 '첫 응답'만 뽑아 유형별로 나눈다
    by_kind = {"extract": [], "clarify": [], "refuse": []}
    for rec in read_jsonl(args.train):
        m = rec["messages"]
        d = parse(m[2]["content"])
        k = kind_of(d)
        if k in by_kind:
            by_kind[k].append(m[:3])
    print({k: len(v) for k, v in by_kind.items()}, "(학습 데이터 첫 응답 유형 분포)")
    rng = random.Random(args.seed)
    samples = [(k, m) for k, v in by_kind.items() for m in rng.sample(v, min(args.n, len(v)))]

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16),
        dtype=torch.bfloat16, device_map={"": 0},
    )
    model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    # ---- 진단 2: 프롬프트 대조 ----
    k0, m0 = samples[0]
    prompt = tok.apply_chat_template(m0[:2], tokenize=False, add_generation_prompt=True, enable_thinking=False)
    ids = tok(prompt, add_special_tokens=False)["input_ids"]
    print("\n[프롬프트 끝부분 repr]", repr(prompt[-80:]))
    print("[프롬프트 끝 토큰 12개]", [tok.decode([t]) for t in ids[-12:]])
    tgt_ids = tok(m0[2]["content"] + "<|im_end|>\n", add_special_tokens=False)["input_ids"]
    print("[정답 첫 토큰 5개]", [tok.decode([t]) for t in tgt_ids[:5]])

    @torch.no_grad()
    def first_token_top(prompt, k=5):
        enc = tok(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
        logits = model(**enc).logits[0, -1].float()
        p = torch.softmax(logits, -1)
        top = torch.topk(p, k)
        return [(tok.decode([i]), round(v.item(), 3)) for v, i in zip(top.values, top.indices)]

    # ---- 진단 1: 학습 문장 생성 ----
    stats = {k: Counter() for k in by_kind}
    rows = []
    for i, (gk, m) in enumerate(samples):
        prompt = tok.apply_chat_template(m[:2], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        enc = tok(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=900, do_sample=False, temperature=None, top_p=None, top_k=None, pad_token_id=tok.pad_token_id)
        text = tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True)
        pk = kind_of(parse(text)) if parse(text) is not None else "invalid"
        stats[gk][pk] += 1
        top = first_token_top(prompt)
        rows.append({"gold_kind": gk, "pred_kind": pk, "user": m[1]["content"], "first_tok_top5": top, "raw": text[:300]})
        print(f"[{i+1}/{len(samples)}] 정답={gk} 예측={pk} 첫토큰={top[:3]}", flush=True)

    print("\n===== 결과: 학습 문장 → 어댑터 응답 유형 =====")
    for gk, c in stats.items():
        tot = sum(c.values())
        print(f"{gk:8s} 정답유형 {tot}건 → {dict(c)}")
    out_path = HERE / "runs" / "diag_train_samples.jsonl"
    out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print("상세 저장:", out_path)


if __name__ == "__main__":
    main()
