"""Q4B(Qwen3-4B) 평가. 병준 eval.py 를 바탕으로 8GB 용으로 조정하고 팀 목표 지표를 더했다.

평가 세트: data/test_set.jsonl 통합 시험 234문항. 기본(--set official111)은 예전 111문항(8B 병준 v1 과 같은 세트라 직접 비교 가능), haechan 123문항은 --set haechan, 전체는 --set all
지표 (정의는 이 스크립트 기준. 팀 정의가 따로 있으면 맞춰야 함)
  - JSON 유효율   : 출력이 JSON 으로 파싱되는 비율                                  (목표 99%)
  - 형태 일치율   : 최상위 키 집합이 정답과 같은 비율 (변환/되묻기/거절 구분)
  - 필드 정확도   : 정답에서 source=user 인 지표(사용자가 말한 것)에 대해
                    id·operator·value·unit 이 모두 맞은 비율                         (목표 90%)
  - 은어 변환율   : kind 에 별칭/오타/구어가 들어간 문항의 완전 일치율               (목표 90%)
  - 완전 일치율   : 파싱한 JSON 이 정답과 완전히 같은 비율 (병준 eval.py 와 같은 기준)
  - kind 별 완전 일치율

사용:
  python -I -X utf8 scripts/eval_q4b.py --tag base                              # 학습 전 기준선
  python -I -X utf8 scripts/eval_q4b.py --adapter outputs/q4b-v1 --tag q4b-v1   # 학습 후
결과: outputs/eval_<tag>.jsonl
"""
import argparse
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

EVAL_FILES = [HERE.parent / "data" / "test_set.jsonl"]  # 통합 시험 세트 234문항(공식 111 + haechan 123). 학습·검증에 쓰지 않는다. 생성: data/scripts/build_test_set.py
SETS = {"official111": ("official111",), "haechan": ("haechan58", "haechan31", "haechan34"), "all": None}  # --set 선택지


def select(rows, name):
    """--set 에 맞는 행만. 기본 official111 은 예전 111문항과 같다(이전 버전 수치와 비교용)."""
    src = SETS[name]
    return rows if src is None else [r for r in rows if r["source"] in src]
SLANG_WORDS = ("별칭", "오타", "구어")


def user_fields(obj):
    """정답/생성 JSON 에서 source=user 지표 → {id: (operator, value, unit)}"""
    out = {}
    if isinstance(obj, dict) and isinstance(obj.get("indicators"), list):
        for x in obj["indicators"]:
            if isinstance(x, dict) and x.get("source") == "user":
                out[x.get("id")] = (x.get("operator"), x.get("value"), x.get("unit"))
    return out


def field_score(gold, pred):
    """(맞은 수, 전체 수): 정답의 user 지표 하나하나를 id·operator·value·unit 으로 비교"""
    g, p = user_fields(gold), user_fields(pred)
    return sum(1 for k, v in g.items() if p.get(k) == v), len(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-4B")
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--max-new", type=int, default=900)
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N문항만 (시험용)")
    ap.add_argument("--set", choices=list(SETS), default="official111", help="시험 범위: official111(기본, 예전 111문항) | haechan(123) | all(234)")
    a = ap.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(a.model, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(
        a.model,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                               bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16),
        dtype=torch.bfloat16, device_map={"": 0})
    if a.adapter:
        model = PeftModel.from_pretrained(model, a.adapter)
    model.eval()

    rows = select([json.loads(l) for p in EVAL_FILES for l in open(p, encoding="utf-8") if l.strip()], a.set)
    if a.limit:
        rows = rows[:a.limit]
    results = []
    for s in range(0, len(rows), a.batch):
        chunk = rows[s:s + a.batch]
        prompts = [tok.apply_chat_template(r["messages"][:2], tokenize=False, add_generation_prompt=True,
                                           enable_thinking=False) for r in chunk]
        enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=a.max_new, do_sample=False)
        for r, g in zip(chunk, gen):
            text = tok.decode(g[enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            results.append({"eval_id": r["eval_id"], "kind": r["kind"], "text": r["text"],
                            "expected": r["output"], "generated": text, "parsed": parsed})
        print(f"{len(results)}/{len(rows)}", flush=True)

    out = HERE.parent / "outputs" / f"eval_{a.tag}.jsonl"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report(results, a.tag, out)


def report(results, tag, out):
    n = len(results)
    valid = sum(r["parsed"] is not None for r in results)
    shape = sum(isinstance(r["parsed"], dict) and set(r["parsed"]) == set(r["expected"]) for r in results)
    exact = sum(r["parsed"] is not None and r["parsed"] == r["expected"] for r in results)
    fo = ft = 0
    for r in results:
        o, t = field_score(r["expected"], r["parsed"])
        fo, ft = fo + o, ft + t
    slang = [r for r in results if any(w in r["kind"] for w in SLANG_WORDS)]
    slang_ok = sum(r["parsed"] is not None and r["parsed"] == r["expected"] for r in slang)
    print(f"\n[{tag}] {n}문항")
    print(f"JSON 유효율   {valid}/{n} = {valid / n:.1%}   (목표 99%)")
    print(f"형태 일치율   {shape}/{n} = {shape / n:.1%}")
    print(f"필드 정확도   {fo}/{ft} = {fo / max(ft, 1):.1%}   (목표 90%)")
    print(f"은어 변환율   {slang_ok}/{len(slang)} = {slang_ok / max(len(slang), 1):.1%}   (목표 90%, 별칭·오타·구어 문항)")
    print(f"완전 일치율   {exact}/{n} = {exact / n:.1%}")
    by = collections.defaultdict(lambda: [0, 0])
    for r in results:
        by[r["kind"]][1] += 1
        by[r["kind"]][0] += r["parsed"] is not None and r["parsed"] == r["expected"]
    for k, (o, t) in sorted(by.items()):
        print(f"  {k}: {o}/{t}")
    print("결과 파일:", out)


if __name__ == "__main__":
    main()
