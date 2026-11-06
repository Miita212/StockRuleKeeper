"""어댑터를 불러와 문장을 직접 넣어 보는 테스트 (대화형).

사용:
    python -X utf8 chat_adapter.py --adapter ~/qwen3-8b-v3-1ep-haechan
    python -X utf8 chat_adapter.py --adapter ~/qwen3-8b-v3-1ep-haechan --text "부채비율 100% 이하인 회사"   # 한 문장만

- 원본 Qwen/Qwen3-8B 를 4bit 로 올리고 어댑터를 얹는다(학습·평가와 같은 방식). GPU 메모리 약 7GB.
- 원본 모델(약 16GB)은 처음 실행할 때 Hugging Face 에서 자동으로 받는다.
- 학습 데이터와 같은 system 문구, enable_thinking=False, 그리디 생성.
- 입력할 때마다 새 대화로 시작한다(되묻기에 이어서 답하는 다중 턴은 지원하지 않음). 끝내려면 빈 줄 또는 Ctrl+C.
"""
import argparse
import json
import time

SYSTEM = "너는 투자 원칙 점검 앱의 도우미야. 사용자의 말을 지표 20개 기준 JSON으로 바꿔. JSON만 출력하고, 종목 추천이나 수익 예측은 하지 않아."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--adapter", required=True, help="adapter_model.safetensors 와 adapter_config.json 이 있는 폴더")
    ap.add_argument("--text", default=None, help="이 문장 하나만 넣고 끝냄")
    ap.add_argument("--max-new", type=int, default=1024)
    args = ap.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                               bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16),
        dtype=torch.bfloat16, device_map={"": 0},
    )
    model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    print("준비 완료. 문장을 입력하세요 (빈 줄이면 종료).\n")

    def ask(text):
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        enc = tok(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
        t = time.time()
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=args.max_new, do_sample=False,
                                 temperature=None, top_p=None, top_k=None, pad_token_id=tok.pad_token_id)
        raw = tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        try:
            d = json.loads(raw)
            kind = "거절" if d.get("refusal") else "되묻기" if d.get("needs_clarification") else "추출" if d.get("indicators") else "기타"
            if kind == "추출":  # 기본값(default)이 아닌, 사용자가 말한 지표만 보여 준다
                shown = {"사용자 지정 지표": [i for i in d["indicators"] if i.get("source") != "default"], "anchors": d.get("anchors")}
            else:
                shown = d
            print(f"[{kind}] ({time.time() - t:.1f}초)")
            print(json.dumps(shown, ensure_ascii=False, indent=1))
        except json.JSONDecodeError:
            print(f"[JSON 아님] ({time.time() - t:.1f}초)\n{raw}")
        print()

    if args.text:
        ask(args.text)
        return
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        ask(text)


if __name__ == "__main__":
    main()
