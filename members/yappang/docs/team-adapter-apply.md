# 팀 8B 어댑터를 얍팡 앱에 적용하기 (Ollama 등록 절차)

작성: 2026-11-06, yappang. 팀원이 학습한 Qwen3-8B LoRA 어댑터를 받을 때마다 이 절차로 Ollama 모델을 만들고 백엔드에 연결한다.
**모든 파일은 WSL 저장소 `/home/user/miniProject/StockRuleKeeper/members/yappang/models/` 아래에 둔다.** 윈도우 경로(`C:\...`, `/mnt/c/...`)는 WSL 저장소와 다른 복사본이다.
이 문서의 경로는 `members/yappang/` 기준이다.

## 1. 한눈에 보기

```
어댑터(LoRA) ──병합──▶ HF 모델(16GB) ──변환──▶ f16 GGUF(16GB) ──양자화──▶ Q4_K_M GGUF(5GB) ──등록──▶ Ollama 모델
 models/<작성자>/<어댑터>   merge_lora_to_hf.py   convert_hf_to_gguf.py   Ollama의 llama-quantize   ollama create
```

- 이 PC(RTX 4060 8GB, Ollama 0.40.8)에서는 Ollama가 **어댑터(ADAPTER)나 safetensors 폴더를 직접 받지 못한다**("LoRA adapters are no longer supported", "MLX runtime is not available"). 그래서 GGUF를 만들어서 넣는다.
- 병준의 `byungjun/finetune_train/swap_adapter.sh`는 같은 순서지만 `/home/ai/...` 경로가 고정이고 llama.cpp 빌드가 필요해서 이 PC에서는 그대로 못 쓴다. 아래는 이 PC에 맞춘 절차다.

## 2. 준비물 (한 번만)

| 항목 | 위치 | 비고 |
|---|---|---|
| 베이스 Qwen3-8B | `models/base/Qwen3-8B/` (약 16GB) | 어댑터를 계속 받을 예정이라 **지우지 않는다**. 없으면 `huggingface_hub.snapshot_download('Qwen/Qwen3-8B', allow_patterns=['*.safetensors','*.json','*.txt','*.jinja'], local_dir='models/base/Qwen3-8B')` |
| 병합 스크립트 | `models/merge_lora_to_hf.py` | 병준 `merge_lora.py`와 같은 계산(`W + (B@A)*alpha/r`), 층 수 검사 포함 |
| llama.cpp 변환 도구 | `models/tools/llama.cpp/` | `git clone --depth 1 https://github.com/ggml-org/llama.cpp`. **빌드는 하지 않는다**(변환 스크립트만 쓴다) |
| 파이썬 환경 | `train_model/.venv` | `pip install gguf sentencepiece`가 추가로 필요했다 |
| 양자화 도구 | `/usr/local/lib/ollama/llama-quantize` | **Ollama가 설치할 때 함께 깔아 준 것**을 쓴다 |

## 3. 절차 (새 어댑터마다)

`<작성자>/<이름>`은 예를 들어 `haechan/qwen3-8b-v3-2ep-haechan`이다. 어댑터 폴더에는 `adapter_model.safetensors`와 `adapter_config.json`(베이스 `Qwen/Qwen3-8B`)이 있어야 한다.

```bash
cd ~/miniProject/StockRuleKeeper/members/yappang/models
PY=../train_model/.venv/bin/python

# 1) 병합 (약 1분). 마지막에 "합친 층 252개 / 어댑터 층 252개 OK"가 나와야 한다
$PY -I -X utf8 merge_lora_to_hf.py --adapter <작성자>/<이름> --base-dir base/Qwen3-8B --out <작성자>/merged-<이름>

# 2) HF -> f16 GGUF (약 1분)
$PY -X utf8 tools/llama.cpp/convert_hf_to_gguf.py <작성자>/merged-<이름> --outtype f16 --outfile <작성자>/merged-<이름>-f16.gguf

# 3) 양자화 Q4_K_M (약 1분, 16GB -> 4.8GB)
/usr/local/lib/ollama/llama-quantize <작성자>/merged-<이름>-f16.gguf <작성자>/merged-<이름>-Q4_K_M.gguf Q4_K_M

# 4) Modelfile 만들기: qwen3:8b 의 TEMPLATE·PARAMETER 를 그대로 쓰고 FROM 만 바꾼다
G=$(realpath <작성자>/merged-<이름>-Q4_K_M.gguf)
ollama show qwen3:8b --modelfile | grep -v '^# ' | sed -E "s#^FROM .*#FROM $G#" > <작성자>/Modelfile.<이름>

# 5) 등록 (GGUF에는 -q 옵션을 못 쓴다. 이미 양자화한 파일을 넣는다)
ollama create <Ollama 모델 이름> -f <작성자>/Modelfile.<이름>

# 6) 임시 파일 정리 (병합 폴더와 f16 GGUF 합쳐 약 32GB. Q4_K_M GGUF는 재등록용으로 남긴다)
rm -r <작성자>/merged-<이름> && rm <작성자>/merged-<이름>-f16.gguf
```

그다음 `backend/.env`의 `LOCAL_LLM_MODEL=<Ollama 모델 이름>`, `LLM_PROVIDER=local`로 바꾸고 **백엔드를 다시 시작**한다.
(`.env`는 gitignore 대상이라 커밋되지 않는다. 되돌리려면 `LLM_PROVIDER=anthropic`.)

### 2026-11-06에 적용한 것
- 어댑터: `models/haechan/qwen3-8b-v3-2ep-haechan/` (haechan v3, 2에폭)
- Ollama 모델: `qwen3-8b-stockrule-v3-2ep` (Q4_K_M, 5.0GB)
- Modelfile: `models/haechan/Modelfile.v3-2ep`

## 4. 확인 방법

```bash
# 모델 직접 호출 (백엔드와 같은 설정: think=false, format=json, temperature 0)
cd members/yappang/train_model
python3 -I scripts/eval_ollama.py --model <Ollama 모델 이름> --tag <태그> --limit 6     # 시험
python3 -I scripts/eval_ollama.py --model <Ollama 모델 이름> --tag <태그>               # 전체 111문항 (약 20분)

# 백엔드 경유
curl -s localhost:8000/health                       # {"llm":"local", ...}
curl -s -X POST localhost:8000/principles/ask -H 'Content-Type: application/json' -d '{"text":"부채비율 100% 이하인 회사만 보고 싶어요"}'
```

- 첫 호출은 모델을 디스크에서 올리느라 30초 안팎 걸린다. 이후 추출 1건은 약 14초(지표 20개 JSON 약 610토큰, 약 43~46 tok/s), 되묻기 약 4초, 거절 약 1초다. VRAM은 약 5.3/8.2GB.
- 평가 지표의 정의는 `eval_q4b.py` 상단 주석을 본다. 팀(haechan·hyeonkyeong) 지표와 정의가 다르므로 비교할 때 어느 정의인지 적는다.

## 5. 주의

- **디스크**: WSL의 가상 디스크 파일이 C: 드라이브에 있고 C: 여유가 약 40GB(92% 사용)다. 병합 폴더와 f16 GGUF가 겹치는 구간에 최대 약 32GB를 쓴다. 지워도 가상 디스크는 줄지 않으니, 한 번에 한 어댑터씩 처리하고 정리한다.
- **막히는 것들(이 PC, Ollama 0.40.8)**: `ollama create`의 `ADAPTER`(LoRA 직접 import), safetensors 폴더 import(MLX 런타임 필요), `-q q4_K_M`(safetensors에만 가능하고 Linux에서는 MLX 필요), GGUF 대상 `-q`(불가). Ollama를 업데이트하면 달라질 수 있다.
- 어댑터가 `Qwen/Qwen3-8B`가 아닌 베이스 기준이면 병합 스크립트가 중단한다.
- 어댑터 가중치와 GGUF는 팀 규칙상 커밋하지 않는다(`models/`는 gitignore 대상).
- 앱의 전체 흐름(되묻기 대화, 수정 요청 `changes` 형식 등)에서 모델 출력이 올바르게 해석되는지는 `hyeonkyeong/backend/llm/principle.py`가 맡는다. 이 문서는 모델 등록까지만 다룬다.

## 6. 평가 결과 (이 모델, 111문항)

모델 `qwen3-8b-stockrule-v3-2ep`(haechan v3 2에폭, Q4_K_M)을 Ollama로 평가했다(2026-11-06). `train_model/scripts/eval_ollama.py`, greedy, `think=false`, `format=json`, 최대 900토큰. 결과 파일은 `train_model/outputs/eval_ollama-v3-2ep-haechan.jsonl`(gitignore).
**Q4B 자체 기준**(`eval_q4b.py`의 정의, 목표는 얍팡 기준) 점수다. haechan·hyeonkyeong 지표와는 정의가 다르다.

| 지표 | 결과 | 목표 |
|---|---|---|
| JSON 유효율 | 111/111 = **100%** | 99% |
| 형태 일치율 | 100/111 = 90.1% | |
| 응답 유형 일치(추출/되묻기/거절) | 106/111 = **95.5%** | |
| 필드 정확도 (사용자가 말한 지표의 id·operator·value·unit 전부 일치) | 47/80 = **58.8%** | 90% |
| 은어 변환율 (별칭·오타·구어 문항 완전일치) | 8/14 = **57.1%** | 90% |
| 완전 일치율 | 54/111 = 48.6% | |
| (참고) haechan 식 필드 단위 정확도, default 포함 | 5239/5360 = 97.7% | 후한 지표 |

**응답 유형 혼동표** (정답 → 모델)
- 추출 67건 → 추출 67 (유형은 전부 맞음)
- 되묻기 30건 → 되묻기 29, 추출 1
- 거절 14건 → 거절 10, 되묻기 4 (20개 밖 지표 거절 8건 중 4건을 되묻기로)

**사용자 지정 지표 80개의 오답 원인** (맞음 47)
| 원인 | 건수 |
|---|---|
| 해당 지표를 `source=user`로 못 잡음 | 13 |
| 값은 맞는데 다른 지표 id에 넣음 (예: 부채비율 150%를 4번 자본잠식률에) | 12 |
| 부등호만 틀림 (`>`인데 `>=`, `<`인데 `<=` 등 경계값) | 4 |
| 값이 틀림 | 4 |

**유형별로 약한 곳**: 되묻기(지표 모호) 0/9, 복수 지표 3/11, 거절(20개 밖) 0/8, 추출 `초과` 1/5·`이내` 2/5. 강한 곳: 되묻기(값 없음) 16/18, 오타·구어 5/8.

**속도** (RTX 4060 8GB, VRAM 약 5.3GB): 평균 9.2초/문항, 약 46 tok/s. 추출 1건은 지표 20개 JSON이라 약 14초.

**해석**: 응답 유형을 고르는 능력과 JSON 형식은 좋지만, **사용자가 말한 지표를 정확한 id에 짚는 능력**이 부족해 Q4B 기준 필드 정확도 58.8%, 은어 변환율 57.1%로 목표 90%에 크게 못 미친다. haechan 식 지표(97.7%)는 default 지표가 대부분 맞아서 높게 나온 것이므로 두 숫자를 같은 선상에서 비교하지 않는다.
