"""Qwen3-4B QLoRA 파인튜닝 (RTX 4060 Laptop 8GB). haechan 의 train_qlora.py 를 복사해 기본값만 바꾼 버전.
변경: 모델 4B, 데이터 yappang/train_model_q4b/data, max-len 1280, batch 1 x accum 16, 출력 outputs/.

데이터: 기본값은 아래 TRAIN_FILE/VAL_FILE (현재 train_fixed.jsonl, val_fixed.jsonl)  (한 줄 = {"messages": [system, user, assistant, ...]})
  데이터를 바꿔 다시 학습할 때는 이 두 상수와 data/DATA_VERSION.md 만 고친다. 실행하면 쓴 파일과 해시를 출력하고
  출력 폴더에 data_used.json 으로 남기므로, 어떤 데이터로 학습한 모델인지 나중에 확인할 수 있다.

loss 범위: assistant 답변 전부. 대화가 여러 턴(S3 되묻기)이면 assistant 턴마다 학습 샘플을 하나씩 만든다.
  - 샘플 = (그 턴 앞까지의 대화 + 생성 시작 표시)  →  정답 = 그 턴의 assistant 답변 + <|im_end|>
  - 생성 시작 표시는 추론 때와 같게 enable_thinking=False 로 만든다(빈 <think> 블록 포함).
  - 템플릿 문법을 건드리지 않아서 transformers 버전이 바뀌어도 마스크가 어긋나지 않는다.

사용:
    python -X utf8 train_qlora.py --dry-run                 # GPU 없이 토큰 길이·샘플 1개만 확인
    python -X utf8 scripts/train_qlora.py --epochs 2              # 학습 (출력 outputs/q4b-v2, 데이터 train_fixed.jsonl)
"""
import argparse
import json
import os
import random
import statistics
from pathlib import Path

# 8GB GPU 에서 긴 샘플(1,100토큰 이상)이 나오면 메모리 조각화로 OOM 이 난다. q4b-v2 첫 시도가 15스텝에서 중단됐다(2026-11-08, 7.66GiB 중 7.38GiB 사용).
# 가장 긴 8개 샘플로 시험한 결과 이 설정에서 최대 6.99GiB 로 들어간다. torch 를 불러오기 전에 정해야 하므로 맨 위에 둔다.
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parent / "data"
# 학습에 쓰는 데이터 파일(기본값). 데이터를 바꾸면 여기와 data/DATA_VERSION.md 를 함께 고친다.
TRAIN_FILE = "train_fixed4.jsonl"
VAL_FILE = "val_fixed4.jsonl"
# 이번 학습의 이름(출력 폴더 outputs/<RUN_NAME>). 이전 학습(q4b-v1: 원본 데이터)과 겹치지 않게 데이터를 바꿀 때마다 새 이름으로 올린다.
# 대응표는 data/DATA_VERSION.md 의 "모델 버전" 절.
RUN_NAME = "q4b-v4"
IGNORE = -100


def data_info(path):
    """쓰는 데이터를 로그에 남기기 위한 (경로, 줄 수, sha256)."""
    import hashlib

    p = Path(path)
    if not p.exists():
        raise SystemExit(f"데이터 파일이 없습니다: {p}")
    raw = p.read_bytes()
    return {"path": str(p), "lines": sum(1 for x in raw.splitlines() if x.strip()), "sha256": hashlib.sha256(raw).hexdigest()}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def check_messages(msgs, where):
    """system 뒤에 user/assistant 가 번갈아 나오고 마지막이 assistant 인지 확인."""
    roles = [m["role"] for m in msgs]
    ok = roles[0] == "system" and roles[-1] == "assistant" and len(roles) >= 3
    ok = ok and all(r == ("user" if i % 2 == 0 else "assistant") for i, r in enumerate(roles[1:]))
    if not ok:
        raise ValueError(f"{where}: 역할 순서가 이상함 {roles}")


def build_examples(records, tokenizer, max_len, where):
    """대화 → (input_ids, labels) 목록. max_len 을 넘으면 자르지 않고 버린다(JSON 이 잘리면 안 되므로)."""
    examples, dropped = [], 0
    for n, rec in enumerate(records, 1):
        msgs = rec["messages"]
        check_messages(msgs, f"{where} {n}번째 줄")
        for k, m in enumerate(msgs):
            if m["role"] != "assistant":
                continue
            prompt = tokenizer.apply_chat_template(
                msgs[:k], tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
            target = m["content"] + "<|im_end|>\n"
            p_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            t_ids = tokenizer(target, add_special_tokens=False)["input_ids"]
            ids = p_ids + t_ids
            if len(ids) > max_len:
                dropped += 1
                continue
            # 마지막 "\n" 은 loss 에서 뺀다(<|im_end|> 까지만 학습)
            labels = [IGNORE] * len(p_ids) + t_ids[:-1] + [IGNORE]
            examples.append({"input_ids": ids, "labels": labels, "turn": sum(1 for x in msgs[:k] if x["role"] == "assistant")})
    return examples, dropped


def describe(name, examples, dropped):
    lens = [len(e["input_ids"]) for e in examples]
    tgt = [sum(1 for x in e["labels"] if x != IGNORE) for e in examples]
    print(f"[{name}] 샘플 {len(examples)}개 (너무 길어 버린 것 {dropped}개)")
    if lens:
        print(f"  전체 길이 평균 {statistics.mean(lens):.0f} / 최대 {max(lens)} 토큰, 정답 길이 평균 {statistics.mean(tgt):.0f} / 최대 {max(tgt)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-4B")
    ap.add_argument("--train", default=str(DEFAULT_DATA / TRAIN_FILE))
    ap.add_argument("--val", default=str(DEFAULT_DATA / VAL_FILE))
    ap.add_argument("--out", default=str(HERE.parent / "outputs" / RUN_NAME))
    ap.add_argument("--max-len", type=int, default=1280)
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=1e-4, help="byungjun 명세 1e-4 (불안정하면 5e-5, 느리면 2e-4)")
    ap.add_argument("--max-steps", type=int, default=-1, help="스모크 테스트용. 예: 50 (-1 이면 에폭 기준)")
    ap.add_argument("--batch", type=int, default=1, help="GPU 한 번에 처리하는 샘플 수 (8GB 기준)")
    ap.add_argument("--accum", type=int, default=16, help="gradient accumulation (실효 배치 = batch x accum = 16)")
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--alpha", type=int, default=64)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true", help="GPU·torch 없이 토큰화만 확인")
    args = ap.parse_args()

    from transformers import AutoTokenizer

    used = {"train": data_info(args.train), "val": data_info(args.val)}
    for k, v in used.items():
        print(f"[데이터] {k}: {v['path']}  ({v['lines']}대화, sha256 {v['sha256'][:12]}…)")
    if not ("_fixed" in Path(args.train).name and "_fixed" in Path(args.val).name):
        print("  ※ '_fixed' 가 아닌 파일로 학습합니다. 의도한 것이 맞는지 확인하세요(data/DATA_VERSION.md 참고).")

    tok = AutoTokenizer.from_pretrained(args.model)
    train_recs, val_recs = read_jsonl(args.train), read_jsonl(args.val)
    train_ex, d1 = build_examples(train_recs, tok, args.max_len, "train")
    val_ex, d2 = build_examples(val_recs, tok, args.max_len, "val")
    print(f"원본 대화: train {len(train_recs)} / val {len(val_recs)}")
    describe("train", train_ex, d1)
    describe("val", val_ex, d2)

    # 샘플 하나를 눈으로 확인: 회색(마스크) 부분은 loss 에 안 들어간다
    rng = random.Random(args.seed)
    picks = rng.sample(train_ex, 3) + rng.sample([x for x in train_ex if x["turn"] > 0], 2)  # 3개 + 다중 턴(2번째 이후 답변) 2개
    for i, e in enumerate(picks, 1):
        learn = [t for t, y in zip(e["input_ids"], e["labels"]) if y != IGNORE]
        print(f"\n--- 샘플 {i} (대화 안 {e['turn'] + 1}번째 답변): 학습 대상 ---")
        print(tok.decode(learn))
        print("    [마스크된 앞부분 끝 60자]", repr(tok.decode([t for t, y in zip(e["input_ids"], e["labels"]) if y == IGNORE])[-60:]))
    ends = sum(1 for e in train_ex if tok.decode([t for t, y in zip(e["input_ids"], e["labels"]) if y != IGNORE]).endswith("<|im_end|>"))
    print(f"\n정답이 <|im_end|> 로 끝나는 샘플: {ends}/{len(train_ex)}  (전부여야 정상)")
    if args.dry_run:
        return

    out_dir = Path(args.out)
    if out_dir.exists() and (list(out_dir.glob("adapter_model*")) or list(out_dir.glob("checkpoint-*"))):
        raise SystemExit(f"이미 학습 결과가 있는 폴더입니다: {out_dir}\n"
                         "이전 학습을 덮어쓰지 않도록 멈춥니다. --out 에 새 이름을 주거나 RUN_NAME 을 바꾸세요.")
    out_dir.mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "data_used.json").write_text(json.dumps(used, ensure_ascii=False, indent=2), encoding="utf-8")

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import BitsAndBytesConfig, Trainer, TrainingArguments, set_seed

    set_seed(args.seed)
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(
        args.model, quantization_config=bnb, dtype=torch.bfloat16, device_map={"": 0}
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.rank,
            lora_alpha=args.alpha,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id

    def collate(batch):
        n = max(len(b["input_ids"]) for b in batch)
        ids = torch.full((len(batch), n), pad_id, dtype=torch.long)
        lab = torch.full((len(batch), n), IGNORE, dtype=torch.long)
        att = torch.zeros((len(batch), n), dtype=torch.long)
        for i, b in enumerate(batch):
            L = len(b["input_ids"])
            ids[i, :L] = torch.tensor(b["input_ids"])
            lab[i, :L] = torch.tensor(b["labels"])
            att[i, :L] = 1
        return {"input_ids": ids, "labels": lab, "attention_mask": att}

    # 0.5 에폭마다 평가·저장 (byungjun 명세). 샘플을 턴 단위로 풀어서 에폭당 스텝은 명세(131)보다 많다.
    steps_per_epoch = max(1, -(-len(train_ex) // (args.batch * args.accum)))
    half_epoch = max(1, steps_per_epoch // 2)
    print(f"에폭당 약 {steps_per_epoch}스텝, 평가·저장 {half_epoch}스텝마다, 전체 약 {int(steps_per_epoch * args.epochs)}스텝")
    targs = TrainingArguments(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=0.05,  # transformers 5.x: 1 미만이면 전체 스텝의 비율
        weight_decay=0.01,
        max_grad_norm=1.0,
        optim="paged_adamw_8bit",
        bf16=True,
        gradient_checkpointing=True,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=half_epoch,
        save_strategy="steps",
        save_steps=half_epoch,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",
        seed=args.seed,
        remove_unused_columns=False,
    )
    trainer = Trainer(model=model, args=targs, train_dataset=train_ex, eval_dataset=val_ex, data_collator=collate)
    trainer.train()
    trainer.save_model(args.out)  # LoRA 어댑터만 저장(합치기·양자화는 따로)
    tok.save_pretrained(args.out)
    print("저장 완료:", args.out)


if __name__ == "__main__":
    main()
