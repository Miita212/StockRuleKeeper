"""S-1 실행기: out/prompts_*.jsonl 의 prompt 를 로컬 모델에 넣어 응답을 저장한다.

D6: 학습 데이터 생성은 로컬 모델로만 한다. 이 스크립트는 외부 API 로 요청을 보내지 않는다
(--backend openai 는 localhost 의 ollama/vLLM/llama.cpp 서버 주소만 허용한다).

출력: 한 줄 = {"prompt_id": "...", "response": "모델 출력 원문"}  (assemble_s1_s2.py 의 --raw 입력)
이미 저장된 prompt_id 는 건너뛰므로 중간에 끊겨도 같은 명령으로 이어서 돌릴 수 있다.

예)
  # 시험 생성 10개 (모드별로 골고루) -> 사람이 raw_trial.jsonl 확인
  python -I run_local_model.py --trial 10 --out raw_trial.jsonl
  # 전체 (4090, bf16)
  python -I run_local_model.py --out raw_outputs.jsonl --batch-size 8
  # 8GB GPU(4060): 4bit (pip install bitsandbytes 필요)
  python -I run_local_model.py --quant 4bit --batch-size 2 --trial 10 --out raw_trial.jsonl
  # ollama 서버 사용
  python -I run_local_model.py --backend openai --base-url http://localhost:11434/v1 --model qwen3:8b ...
"""
import argparse
import json
import random
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
DEFAULT_PROMPTS = [HERE / "out" / "prompts_s1.jsonl", HERE / "out" / "prompts_s2.jsonl"]
DEFAULT_MODEL = "Qwen/Qwen3-8B"


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_prompts(paths):
    rows, seen = [], set()
    for p in paths:
        for r in read_jsonl(p):
            if r["prompt_id"] in seen:
                sys.exit(f"prompt_id 중복: {r['prompt_id']}")
            seen.add(r["prompt_id"])
            rows.append(r)
    return rows


def pick_trial(rows, k, seed):
    """모드별로 골고루 k개를 고른다 (시험 생성은 모든 모드를 한 번씩 보는 게 목적)."""
    by_mode = defaultdict(list)
    for r in rows:
        by_mode[r["mode"]].append(r)
    rng = random.Random(seed)
    for v in by_mode.values():
        rng.shuffle(v)
    picked, modes = [], sorted(by_mode)
    while len(picked) < k and any(by_mode.values()):
        for m in modes:
            if by_mode[m] and len(picked) < k:
                picked.append(by_mode[m].pop())
    return picked


class HFBackend:
    def __init__(self, model, quant, max_new_tokens, temperature, top_p):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            sys.exit("transformers 가 없다: pip install transformers accelerate (4bit 는 bitsandbytes 도)")
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        kw = {"device_map": "auto"}
        if quant == "4bit":
            from transformers import BitsAndBytesConfig
            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16)
        else:
            kw["torch_dtype"] = torch.bfloat16
        self.model = AutoModelForCausalLM.from_pretrained(model, **kw).eval()
        self.gen_kw = dict(max_new_tokens=max_new_tokens, do_sample=True,
                           temperature=temperature, top_p=top_p, top_k=20,
                           pad_token_id=self.tok.pad_token_id)

    def generate(self, prompts):
        texts = [self.tok.apply_chat_template(
            [{"role": "user", "content": p}], tokenize=False,
            add_generation_prompt=True, enable_thinking=False)  # D4: 사고 모드 끔
            for p in prompts]
        enc = self.tok(texts, return_tensors="pt", padding=True).to(self.model.device)
        with self.torch.inference_mode():
            out = self.model.generate(**enc, **self.gen_kw)
        new = out[:, enc["input_ids"].shape[1]:]
        return [self.tok.decode(x, skip_special_tokens=True).strip() for x in new]


class OpenAILocalBackend:
    """localhost 의 OpenAI 호환 서버(ollama, vLLM, llama.cpp). 원격 주소는 거부한다."""

    def __init__(self, base_url, model, max_new_tokens, temperature, top_p):
        host = urlparse(base_url).hostname
        if host not in ("localhost", "127.0.0.1", "::1"):
            sys.exit(f"D6: 로컬 서버만 허용한다 (받은 주소: {base_url})")
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.body = dict(model=model, max_tokens=max_new_tokens,
                         temperature=temperature, top_p=top_p)

    def generate(self, prompts):
        res = []
        for p in prompts:
            body = dict(self.body, messages=[{"role": "user", "content": p}],
                        chat_template_kwargs={"enable_thinking": False})
            req = urllib.request.Request(
                self.url, json.dumps(body).encode("utf-8"),
                {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                msg = json.load(r)["choices"][0]["message"]["content"]
            res.append(msg.strip())
        return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--prompts", nargs="+", type=Path, default=DEFAULT_PROMPTS)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--backend", choices=["hf", "openai"], default="hf")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--quant", choices=["none", "4bit"], default="none")
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--max-new-tokens", type=int, default=2500)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--trial", type=int, help="모드별로 골고루 N개만 (시험 생성)")
    ap.add_argument("--limit", type=int, help="앞에서 N개만")
    ap.add_argument("--modes", nargs="+", help="특정 mode 만 (예: no_value seed)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="모델 없이 대상 개수만 출력")
    a = ap.parse_args()

    rows = load_prompts(a.prompts)
    if a.modes:
        rows = [r for r in rows if r["mode"] in a.modes]
    if a.trial:
        rows = pick_trial(rows, a.trial, a.seed)
    if a.limit:
        rows = rows[:a.limit]

    done = set()
    if a.out.exists():
        done = {json.loads(l)["prompt_id"] for l in open(a.out, encoding="utf-8") if l.strip()}
    todo = [r for r in rows if r["prompt_id"] not in done]
    print(f"대상 {len(rows)}개, 이미 완료 {len(rows) - len(todo)}개, 남음 {len(todo)}개")
    if a.dry_run or not todo:
        for r in todo[:20]:
            print(" ", r["prompt_id"], r["mode"])
        return

    if a.backend == "hf":
        be = HFBackend(a.model, a.quant, a.max_new_tokens, a.temperature, a.top_p)
    else:
        be = OpenAILocalBackend(a.base_url, a.model, a.max_new_tokens, a.temperature, a.top_p)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    t0, n = time.time(), 0
    with open(a.out, "a", encoding="utf-8") as f:
        for i in range(0, len(todo), a.batch_size):
            batch = todo[i:i + a.batch_size]
            resp = be.generate([r["prompt"] for r in batch])
            for r, text in zip(batch, resp):
                f.write(json.dumps({"prompt_id": r["prompt_id"], "response": text},
                                   ensure_ascii=False) + "\n")
            f.flush()
            n += len(batch)
            el = time.time() - t0
            print(f"[{n}/{len(todo)}] {el/60:.1f}분 경과, 남은 예상 {el/n*(len(todo)-n)/60:.1f}분", flush=True)


if __name__ == "__main__":
    main()
