# Qwen3-8B 파인튜닝 실행 가이드 (4090 서버)

이 폴더(`finetune/`)를 통째로 서버에 옮긴 뒤 이 순서대로 실행한다.
학습할 것은 FR-01 "말 번역기"다. 자연어 원칙을 지표 20개 JSON으로 바꾸고, 모호하면 되묻고, 추천 요청은 거절하고, 용어를 쉽게 설명한다.
설정값은 병준 명세(`byungjun/finetune_merged/파인튜닝_설정값_명세.md`)를 그대로 따른다.

| 순서 | 할 일 | 어디서 | 걸리는 시간(추정) |
|---|---|---|---|
| 1 | 폴더 옮기기 | 노트북 | 1분 |
| 2 | 접속·tmux | 서버 | - |
| 3 | 환경 설치 + 모델 다운로드 | 서버 | 10~30분 |
| 4 | 사전 점검 | 서버 | 1분 |
| 5 | 학습 전 점수(기준선) | 서버 | 10~20분 |
| 6 | 스모크 테스트(50스텝) | 서버 | 5~15분 |
| 7 | 본 학습(4에폭) | 서버 | 6번 결과로 계산 |
| 8 | 체크포인트 고르기 | 서버 | 체크포인트당 10~20분 |
| 9 | GGUF로 내보내기 | 서버 | 15~30분 |
| 10 | 노트북으로 가져와 Ollama 등록 | 노트북 | 10분 |
| 11 | 백엔드·앱에서 확인 | 노트북 | 10분 |

시간은 모두 추정이다. 6번 스모크 테스트에서 실제 속도를 잰다.

---

## 1. 폴더 옮기기 (노트북에서)

```bash
cd /home/user/StockRuleKeeper/StockRuleKeeper/members/hyeonkyeong
rsync -av --exclude outputs/ --exclude models/ --exclude tools/ --exclude __pycache__/ finetune ws3:~/
```
- `ws3`는 서버 주소다. 별칭이 없으면 `사용자명@서버IP`로 바꾼다.
- rsync가 없으면 `scp -r finetune ws3:~/`를 쓴다. 폴더가 4MB 정도라 금방 끝난다.
- **나중에 코드를 고쳐 다시 보낼 때도 같은 명령을 쓴다.** 서버의 `outputs/`·`models/`는 건드리지 않는다.

## 2. 접속·tmux (서버에서)

```bash
ssh ws3
tmux new -s ft        # 학습은 꼭 tmux 안에서 (와이파이가 끊겨도 계속 돈다)
cd ~/finetune
```
- 끊긴 뒤 다시 들어갈 때는 `ssh ws3` 후 `tmux attach -t ft`를 입력한다.
- tmux에서 잠깐 빠져나오려면(학습은 계속 돈다) `Ctrl+b`를 누른 뒤 `d`를 누른다.
- tmux가 없으면 `nohup 명령 > 로그.txt 2>&1 &`으로 대신한다.

## 3. 환경 설치 + 모델 다운로드

```bash
bash setup.sh
```
**정상이면** 마지막에 다음이 보인다.
```
torch==2.x  transformers==5.17.0 ...
cuda_available: True
gpu: NVIDIA GeForce RTX 4090 | bf16: True
...  model-00001-of-00005.safetensors ...
완료. 다음: conda activate srk-ft && python preflight.py
```
처음 `[1/5]`에서 출력되는 것도 읽어 본다.
- **디스크**는 60GB 이상 남아 있어야 한다.
- **GPU를 쓰는 프로세스**가 있으면 공용 서버이니 사용자에게 먼저 확인한다.
- **`!!` 표시**가 붙은 줄이 있으면 문제가 있다는 뜻이다.

**안 되면**
| 증상 | 할 일 |
|---|---|
| `cuda_available: False` | 서버 드라이버가 오래된 것이다. `nvidia-smi` 오른쪽 위 "CUDA Version"을 보고 맞는 torch를 다시 설치한다. 예: 12.8이면 `conda activate srk-ft && pip install torch --index-url https://download.pytorch.org/whl/cu128` |
| `!! conda 없음` | Miniconda를 설치한다: `wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && bash Miniconda3-latest-Linux-x86_64.sh -b && source ~/miniconda3/bin/activate`. 그다음 다시 `bash setup.sh` |
| huggingface.co 접속 안 됨 | 노트북에서 모델을 받아 옮긴다: 노트북에서 `hf download Qwen/Qwen3-8B --local-dir qwen3-8b` → `rsync -av qwen3-8b/ ws3:~/finetune/models/Qwen3-8B/` → 서버에서 `bash setup.sh --skip-model` |
| `!! cmake 없음` 등 | 무시해도 된다. cmake는 pip로 설치된다. git·gcc·make가 없으면 9번(내보내기)에서 막히므로 서버 관리자에게 요청한다 |

이후 새 터미널을 열 때마다 `conda activate srk-ft`를 먼저 입력한다.

## 4. 사전 점검

```bash
python preflight.py
```
**정상이면**
- `1. 토큰 길이`: train `대화 2090개 → 샘플 2515개`, val `111개 → 135개`, 모두 `잘리는 샘플 0건`, 최대 약 1,180토큰
  (턴별 분할: S3 되묻기처럼 답이 여러 번인 대화는 답마다 샘플 1개)
- `2. 마스크 샘플`: `[[ ]]` 안에 **assistant 답변만** 있다. S3 대화 하나가 샘플 2개(1번째 답 = 되묻기, 2번째 답 = 확정)로 나오고, 둘 다 입력 끝이 `<think>\n\n</think>`다.
- `3. 전체 마스크 검사`: `이상 0건`

노트북에서 Qwen3-1.7B 토크나이저로 미리 돌렸을 때 모두 정상이었다. 결과가 다르면 학습하지 말고 멈춘다.

## 5. 학습 전 점수 (기준선)

```bash
python evaluate.py --model models/Qwen3-8B --name base
```
- 결과는 `outputs/eval_base/` 폴더에 저장된다.
  - `summary.json`: 점수 요약
  - `results.csv`: 문제별 맞음/틀림
  - `predictions.jsonl`: 모델이 실제로 쓴 답
- 학습 전 모델은 우리 JSON 형식을 모르므로 `type_correct`·`anchor_exact`가 0%에 가까운 게 정상이다. 이 점수가 "수정 전" 비교 자료가 된다.
- **안 되면 (OOM):** `--batch_size 4`로 줄인다.

## 6. 스모크 테스트 (50스텝)

```bash
python train.py --max_steps 50 --eval_steps 25 --out outputs/smoke 2>&1 | tee outputs/smoke.log
```
**정상이면** 마지막 `===== 요약 =====`에 다음이 나온다.
```
걸린 시간 X분, 스텝 50개, 스텝당 Y초
최대 VRAM Z GB          ← 24GB보다 충분히 작아야 함 (예상 12~18GB)
val loss:
  step   25 ...  a
  step   50 ...  b      ← a보다 작아야 함
```
- **본 학습 시간:** `스텝당 Y초 × 632 + 평가 8회`로 계산한다. 4에폭은 632스텝이다(에폭당 158스텝).
- `loss`가 계속 0에 가깝거나 `nan`이면 멈추고 확인한다. 4번 마스크 출력을 다시 보면 된다.

**안 되면 (OOM):** 배치를 반으로 줄이고 누적을 2배로 늘린다. 유효 배치 16은 그대로다.
```bash
python train.py --max_steps 50 --eval_steps 25 --batch_size 2 --grad_accum 8 --out outputs/smoke
```
그다음 7번 본 학습에도 같은 옵션을 붙인다.

## 7. 본 학습 (4에폭)

```bash
python train.py --out outputs/run1 2>&1 | tee outputs/run1.log
```
- **진행 보기:** 다른 tmux 창(`Ctrl+b` 누른 뒤 `c`)에서 `tail -f outputs/run1.log`, GPU는 `watch -n 5 nvidia-smi`로 본다.
- 79스텝(0.5에폭)마다 `eval_loss`가 찍히고 `outputs/run1/checkpoint-79`, `-158` 식으로 저장된다. 4에폭이면 체크포인트가 8개다.
- **끊겼을 때** 마지막 체크포인트에서 이어 하려면 `python train.py --out outputs/run1 --resume 2>&1 | tee -a outputs/run1.log`를 실행한다.
- 끝나면 요약에 `best 체크포인트`(val loss가 가장 낮은 것)가 나오고, 그 내용이 `outputs/run1/best/`에 복사된다.

## 8. 체크포인트 고르기

val loss만 보고 고르지 않는다. **val loss가 가장 낮은 것과 그 앞뒤 체크포인트**, 2~3개를 실제로 풀게 해서 비교한다.
```bash
python evaluate.py --model models/Qwen3-8B --adapter outputs/run1/checkpoint-316
python evaluate.py --model models/Qwen3-8B --adapter outputs/run1/checkpoint-395
python evaluate.py --model models/Qwen3-8B --adapter outputs/run1/checkpoint-474
```
(번호는 예시다. 실제 번호는 `ls outputs/run1`이나 7번 요약의 val loss 표를 보고 정한다.)

**고르는 기준** (`outputs/eval_checkpoint-*/summary.json`)
1. `json_valid`: 99% 이상
2. `type_correct`: 지표 / 되묻기 / 거절을 맞게 골랐는지
3. `anchor_exact`: 사용자가 말한 지표의 값·부등호가 맞는지 (핵심)
4. `clarify_correct`, `refusal_correct`

팀 목표는 JSON 유효율 99%, 필드 정확도 90%다. 많이 미달하면 few-shot으로 돌리는 것을 팀과 상의한다.
기록할 것: 5번 기준선 점수와 고른 체크포인트 점수. 발표의 "수정 전/후 비교" 자료가 된다.

## 9. GGUF로 내보내기

```bash
python export.py --adapter outputs/run1/checkpoint-XXX      # 8번에서 고른 것
```
- 처음 실행할 때 llama.cpp를 `tools/`에 받아 빌드한다. 몇 분 걸린다.
- 병합은 CPU에서 한다. 서버 RAM이 32GB 이상이면 안전하다.

**정상이면** `outputs/export/`에 다음이 생긴다.
```
qwen3-8b-stockrule-Q4_K_M.gguf   약 5GB   ← 가져갈 것
Modelfile                                 ← 가져갈 것
qwen3-8b-stockrule-Q8_0.gguf     약 9GB   (비교용, 선택)
Modelfile.q8                              (비교용, 선택)
merged/, *-bf16.gguf                      (중간 파일, 가져갈 필요 없음)
```

**안 되면**
| 증상 | 할 일 |
|---|---|
| GitHub 접속 안 됨 (git clone 실패) | 노트북에서 `git clone --depth 1 https://github.com/ggml-org/llama.cpp`로 받은 뒤 `rsync -av llama.cpp ws3:~/finetune/tools/` |
| RAM 부족으로 죽음 | `export.py`에서 병합 부분의 `device_map="cpu"`를 `"cuda"`로 바꾼다. 학습이 끝나 GPU가 비어 있을 때만 |

## 10. 노트북으로 가져와 Ollama 등록 (노트북에서)

```bash
mkdir -p ~/srk-model && cd ~/srk-model
rsync -av --progress ws3:~/finetune/outputs/export/qwen3-8b-stockrule-Q4_K_M.gguf ws3:~/finetune/outputs/export/Modelfile .
ollama create qwen3-8b-stockrule -f Modelfile
ollama run qwen3-8b-stockrule "부채비율 100% 이하인 회사"     # 간단 확인: JSON이 나오면 됨
```
- **압축(4비트) 뒤에도 점수가 유지되는지 확인한다.** 노트북에서 `finetune` 폴더를 기준으로 실행한다.
```bash
cd /home/user/StockRuleKeeper/StockRuleKeeper/members/hyeonkyeong/finetune
conda activate llm-torch
python evaluate.py --ollama qwen3-8b-stockrule
```
  8번에서 고른 체크포인트 점수보다 크게 떨어지면 Q8_0으로 바꿔 비교한다. 이때는 `Modelfile.q8`로 `ollama create`를 다시 한다.
- 학습 형식과 Ollama 입력 형식이 같은 것은 1.7B로 확인했다. 입력 토큰 수가 단일 턴·다중 턴 모두 일치했다.
- 서버의 `outputs/run1/best/`(LoRA 어댑터, 약 170MB)도 노트북에 백업해 둔다.

## 11. 백엔드·앱에서 확인 (노트북에서)

`members/hyeonkyeong/backend/.env`를 다음과 같이 바꾼다.
```
LLM_PROVIDER=local
LOCAL_LLM_URL=http://localhost:11434
LOCAL_LLM_MODEL=qwen3-8b-stockrule
```
백엔드 폴더에서 리눅스용 Python 환경으로 확인한다.
```bash
python -X utf8 scripts/test_principles.py --live      # 실제 모델로 문장 몇 개 변환
python -X utf8 -m uvicorn main:app --host 0.0.0.0 --port 8000
```
- `/health`의 `llm`이 `local`로 나와야 한다.
- 앱에서 세 가지를 직접 해 본다: 원칙 만들기("빚 많은 회사 싫어요" → 되묻기 → 선택), 원칙 수정, 추천 요청 거절.
- 응답이 10초 안에 오는지도 본다. 성능 기준이 10초다.
- 문제가 있으면 `LLM_PROVIDER=anthropic`으로 되돌리면 바로 Haiku로 돌아간다.

---

## 문제 해결 모음

| 증상 | 원인 | 할 일 |
|---|---|---|
| `CUDA out of memory` | 배치가 큼, 다른 사람이 GPU 사용 중 | `nvidia-smi` 확인 → `--batch_size 2 --grad_accum 8` |
| SSH가 끊겨 학습이 멈춤 | tmux 밖에서 실행함 | tmux 안에서 `--resume`으로 이어서 |
| 출력 JSON이 중간에 끊김 | `max_new_tokens` 부족 | `evaluate.py --max_new_tokens 1536` |
| 출력 앞에 `<think>` 내용이 나옴 | 학습·추론에서 thinking 설정이 다름 | Ollama 호출에 `"think": false`가 있는지, Modelfile 템플릿을 고치지 않았는지 확인 |
| 학습 loss가 0에 가까움 | 마스크가 잘못돼 질문까지 외움 | `preflight.py` 2번 출력 다시 확인 |
| 되묻기·거절이 거의 안 나옴 | system 문구가 학습 때와 다름 | 백엔드 `llm/principle.py`의 system 문구가 `data/train.jsonl`과 글자까지 같은지 확인 |
| 지표는 맞는데 값·부등호가 틀림 | 말→JSON 데이터(SEED 195건)가 적음 | 팀과 상의: S1·S2 데이터 추가 후 재학습 |
| Ollama에서 점수가 크게 떨어짐 | 4비트 압축 손실 | `Modelfile.q8`(Q8_0)로 비교 |

## 폴더 구성

| 파일 | 하는 일 |
|---|---|
| `setup.sh`, `requirements.txt` | 환경 설치, 모델 다운로드 |
| `common.py` | 턴별 분할 샘플·마스크 만들기 (preflight·train·evaluate 공통) |
| `preflight.py` | 토큰 길이·마스크 점검 |
| `train.py` | QLoRA 학습 (기본값 = 병준 명세) |
| `evaluate.py` | 평가 111건 채점 (`--model` / `--adapter` / `--ollama`) |
| `export.py` | 병합 → GGUF(Q4_K_M, Q8_0) + Modelfile |
| `data/` | train 2,090 / val 111 (병준 `finetune_merged` 복사), eval 111 (현경 `eval_*` 합침) |
| `outputs/` | 결과 (커밋 안 함) |

노트북(WSL, Qwen3-1.7B)에서 preflight → train(4스텝) → evaluate(HF·LoRA·Ollama) → export → Ollama 등록까지 전체 흐름을 한 번 돌려서 확인했다(2026-11-05). 8B로 서버에서 실행한 적은 아직 없다.
