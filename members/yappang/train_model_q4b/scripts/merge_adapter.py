"""LoRA 어댑터를 원본 모델에 합쳐 저장한다 (GGUF 변환 준비).

QLoRA 어댑터는 NF4 로 양자화된 가중치 위에서 학습됐다. --nf4 를 주면 학습 때와 같은 NF4 가중치를
bf16 으로 복원한 값에 합친다. 이 옵션 없이 bf16 원본에 합치면 학습 때와 다른 모델이 된다.

사용: python -X utf8 scripts/merge_adapter.py --nf4 --adapter outputs/q4b-v1 --out outputs/q4b-v1-merged-nf4
"""
import argparse

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="Qwen/Qwen3-4B")
ap.add_argument("--adapter", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--nf4", action="store_true")
a = ap.parse_args()


def load_dequantized_nf4(name):
    """train_qlora.py 와 같은 설정으로 NF4 로드 후 Linear4bit 를 bf16 Linear 로 되돌린다."""
    import bitsandbytes as bnb

    model = AutoModelForCausalLM.from_pretrained(
        name,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                               bnb_4bit_use_double_quant=True,
                                               bnb_4bit_compute_dtype=torch.bfloat16),
        dtype=torch.bfloat16, device_map={"": 0})
    count = 0
    for parent in list(model.modules()):
        for child_name, child in list(parent.named_children()):
            if isinstance(child, bnb.nn.Linear4bit):
                w = bnb.functional.dequantize_4bit(child.weight.data, child.weight.quant_state)
                lin = torch.nn.Linear(child.in_features, child.out_features, bias=child.bias is not None,
                                      dtype=torch.bfloat16, device="cpu")
                lin.weight.data.copy_(w.to("cpu", torch.bfloat16))
                if child.bias is not None:
                    lin.bias.data.copy_(child.bias.data.cpu())
                setattr(parent, child_name, lin)
                count += 1
    print("복원한 Linear4bit:", count)
    model = model.to("cpu")
    for attr in ("quantization_method", "hf_quantizer", "is_quantized", "is_loaded_in_4bit"):
        if hasattr(model, attr):
            try:
                delattr(model, attr)
            except AttributeError:
                pass
    model.config.__dict__.pop("quantization_config", None)
    torch.cuda.empty_cache()
    return model


if a.nf4:
    model = load_dequantized_nf4(a.model)
else:
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={"": "cpu"})
model = PeftModel.from_pretrained(model, a.adapter).merge_and_unload()
model.save_pretrained(a.out, safe_serialization=True)
AutoTokenizer.from_pretrained(a.adapter).save_pretrained(a.out)
print("병합 완료:", a.out)
