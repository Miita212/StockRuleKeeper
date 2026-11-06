"""평가 세트(111건)로 기준선(학습 전 Qwen3-8B + few-shot)과 학습 후 체크포인트를 같은 조건에서 비교한다.

  - 평가 세트: members/hyeonkyeong/data/eval_*.jsonl  ({text, output(정답), messages[system,user,assistant]})
  - 생성: 그리디(temperature 0), enable_thinking=False (학습과 동일), 학습 때와 같은 system 문구
  - 기준선: LoRA 를 끄고, 학습 데이터(train.jsonl)에서 뽑은 예시 4개를 few-shot 으로 붙인다
  - 모델은 한 번만 4비트로 올리고 어댑터를 바꿔 끼우며 평가한다

사용:
    python -X utf8 eval_model.py --limit 6 --variants base ckpt=runs/qwen3-8b-v1/checkpoint-395   # 동작 확인
    python -X utf8 eval_model.py --out runs/eval                                                   # 전체(기준선 + 체크포인트 3개)
"""
import argparse
import glob
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEMBERS = HERE.parent.parent  # .../members
EVAL_GLOB = str(MEMBERS / "hyeonkyeong" / "data" / "eval_*.jsonl")
TRAIN = MEMBERS / "byungjun" / "finetune_merged" / "train.jsonl"
FIELDS = ["operator", "value", "unit", "source"]


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


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


def parse(text):
    try:
        v = json.loads(text.strip())
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def score(gold, pred):
    """한 건 채점. 반환: dict (집계용 숫자들)."""
    gk = kind_of(gold)
    s = {"gold_kind": gk, "valid": pred is not None}
    pk = kind_of(pred) if pred is not None else "invalid"
    s["pred_kind"] = pk
    s["kind_ok"] = pk == gk
    if gk == "extract" and pk == "extract":
        pmap = {i.get("id"): i for i in pred.get("indicators", []) if isinstance(i, dict)}
        n_field = ok_field = n_ind = ok_ind = 0
        u_n = u_ok = 0
        for g in gold["indicators"]:
            p = pmap.get(g["id"], {})
            keys = FIELDS + [k for k in ("period_months",) if k in g or k in p]
            matches = [eq(g.get(k), p.get(k)) for k in keys]
            n_field += len(matches)
            ok_field += sum(matches)
            n_ind += 1
            ok_ind += all(matches)
            if g.get("source") == "user":
                u_n += 1
                u_ok += all(matches)
        s.update(
            field_n=n_field, field_ok=ok_field,
            exact=(ok_ind == n_ind and len(pmap) == n_ind and sorted(pred.get("anchors", [])) == sorted(gold.get("anchors", []))),
            user_n=u_n, user_ok=u_ok,
            # 사용자가 말하지 않은 지표를 건드렸는지(기본값이 바뀌었는지)
            default_broken=sum(1 for g in gold["indicators"] if g.get("source") == "default" and not all(eq(g.get(k), pmap.get(g["id"], {}).get(k)) for k in FIELDS)),
        )
    elif gk == "extract":
        s.update(field_n=len(gold["indicators"]) * len(FIELDS), field_ok=0, exact=False,
                 user_n=sum(1 for g in gold["indicators"] if g.get("source") == "user"), user_ok=0, default_broken=0)
    if gk == "clarify" and pk == "clarify":
        s["reason_ok"] = pred.get("reason") == gold.get("reason")
        s["target_ok"] = pred.get("indicator_id") == gold.get("indicator_id")
    if gk == "refuse" and pk == "refuse":
        s["refuse_empty_ok"] = pred.get("indicators") == []
    return s


def summarize(rows):
    """rows: [{kind, score}] → 요약 dict."""
    def rate(a, b):
        return round(100 * a / b, 1) if b else None

    n = len(rows)
    sc = [r["score"] for r in rows]
    ext = [x for x in sc if x["gold_kind"] == "extract"]
    cla = [x for x in sc if x["gold_kind"] == "clarify"]
    ref = [x for x in sc if x["gold_kind"] == "refuse"]
    out = {
        "건수": n,
        "JSON 유효율": rate(sum(x["valid"] for x in sc), n),
        "응답 유형 일치(추출/되묻기/거절)": rate(sum(x["kind_ok"] for x in sc), n),
        f"추출 전체 일치 ({len(ext)}건)": rate(sum(x.get("exact", False) for x in ext), len(ext)),
        "추출 필드 정확도": rate(sum(x.get("field_ok", 0) for x in ext), sum(x.get("field_n", 0) for x in ext)),
        "추출 사용자 지정 지표 정확도": rate(sum(x.get("user_ok", 0) for x in ext), sum(x.get("user_n", 0) for x in ext)),
        "기본값이 바뀐 지표 수(합)": sum(x.get("default_broken", 0) for x in ext),
        f"되묻기 판단 ({len(cla)}건)": rate(sum(x["kind_ok"] for x in cla), len(cla)),
        "되묻기 사유 일치": rate(sum(x.get("reason_ok", False) for x in cla), len(cla)),
        "되묻기 대상 지표 일치": rate(sum(x.get("target_ok", False) for x in cla), len(cla)),
        f"거절 정확도 ({len(ref)}건)": rate(sum(x["kind_ok"] for x in ref), len(ref)),
        # 잘못 되묻기/거절한 비율: 추출해야 하는데 다른 유형으로 답한 경우
        "불필요한 되묻기·거절 (추출 건 중)": rate(sum(1 for x in ext if x["pred_kind"] in ("clarify", "refuse")), len(ext)),
    }
    return out


def build_fewshot(k=4):
    """학습 데이터에서 유형별로 가장 짧은 3메시지 대화를 골라 few-shot 으로 쓴다."""
    recs = [r["messages"] for r in read_jsonl(TRAIN) if len(r["messages"]) == 3]
    picked = {}
    for m in sorted(recs, key=lambda m: len(m[2]["content"])):
        d = parse(m[2]["content"])
        key = kind_of(d)
        if key in ("extract", "clarify", "refuse") and key not in picked and (key != "extract" or len(d["indicators"]) == 20):
            picked[key] = m
    shots = [picked[k_] for k_ in ("extract", "clarify", "refuse") if k_ in picked]
    # 복수 지표 예시 하나 더 (user 지정이 2개 이상인 추출)
    for m in sorted(recs, key=lambda m: len(m[2]["content"])):
        d = parse(m[2]["content"])
        if kind_of(d) == "extract" and sum(1 for i in d["indicators"] if i.get("source") == "user") >= 2:
            shots.append(m)
            break
    return shots[:k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--variants", nargs="*", help="base 또는 이름=어댑터경로. 기본: base + runs/qwen3-8b-v1/checkpoint-*")
    ap.add_argument("--out", default=str(HERE / "runs" / "eval"))
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N건만 (동작 확인용)")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--max-new", type=int, default=1024)
    args = ap.parse_args()

    rows = [r for f in sorted(glob.glob(EVAL_GLOB)) for r in read_jsonl(f)]
    if args.limit:
        rows = rows[: args.limit]
    variants = args.variants
    if not variants:
        cks = sorted(glob.glob(str(HERE / "runs" / "qwen3-8b-v1" / "checkpoint-*")), key=lambda p: int(p.rsplit("-", 1)[1]))
        variants = ["base"] + [f"ckpt{p.rsplit('-', 1)[1]}={p}" for p in cks]
    print(f"평가 {len(rows)}건, 변형: {variants}")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(args.model)
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16),
        dtype=torch.bfloat16, device_map={"": 0},
    )
    model.eval()
    shots = build_fewshot()
    print(f"few-shot 예시 {len(shots)}개 (기준선에만 사용)")

    def make_prompt(r, fewshot):
        sysmsg, user = r["messages"][0], r["messages"][1]
        msgs = [sysmsg]
        if fewshot:
            for m in shots:
                msgs += [m[1], m[2]]
        msgs.append(user)
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)

    @torch.no_grad()
    def generate(prompts):
        order = sorted(range(len(prompts)), key=lambda i: len(prompts[i]))
        res = [None] * len(prompts)
        for b in range(0, len(order), args.batch):
            idx = order[b : b + args.batch]
            enc = tok([prompts[i] for i in idx], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            out = model.generate(**enc, max_new_tokens=args.max_new, do_sample=False, temperature=None, top_p=None, top_k=None, pad_token_id=tok.pad_token_id)
            for j, i in enumerate(idx):
                res[i] = tok.decode(out[j, enc["input_ids"].shape[1]:], skip_special_tokens=True)
            print(f"  {min(b + args.batch, len(order))}/{len(order)}", flush=True)
        return res

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    loaded = False
    summaries = {}
    for v in variants:
        name, _, path = v.partition("=")
        t0 = time.time()
        print(f"\n=== {name} ===", flush=True)
        if name == "base":
            fewshot = True
            if loaded:
                ctx = model.disable_adapter()
            else:
                ctx = None
        else:
            fewshot = False
            if not loaded:
                model = PeftModel.from_pretrained(model, path, adapter_name=name)
                loaded = True
            elif name not in model.peft_config:
                model.load_adapter(path, adapter_name=name)
            model.set_adapter(name)
            ctx = None
        prompts = [make_prompt(r, fewshot) for r in rows]
        if name == "base" and loaded:
            with model.disable_adapter():
                gens = generate(prompts)
        else:
            gens = generate(prompts)
        recs = []
        for r, g in zip(rows, gens):
            pred = parse(g)
            recs.append({"id": r["id"], "kind": r["kind"], "text": r["text"], "gold": r["output"], "raw": g, "score": score(r["output"], pred)})
        (outdir / f"{name}.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in recs) + "\n", encoding="utf-8")
        summaries[name] = summarize(recs)
        print(f"{name} 완료 ({time.time() - t0:.0f}초)")
        print(json.dumps(summaries[name], ensure_ascii=False, indent=1), flush=True)
        (outdir / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== 비교 =====")
    keys = list(next(iter(summaries.values())).keys())
    names = list(summaries)
    print("항목".ljust(36) + "".join(n.rjust(12) for n in names))
    for k in keys:
        print(k.ljust(36) + "".join(str(summaries[n][k]).rjust(12) for n in names))


if __name__ == "__main__":
    main()
