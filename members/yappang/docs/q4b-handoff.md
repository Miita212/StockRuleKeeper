# Q4B 학습 인수인계 (다른 노트북의 Claude용)

작성: 2026-11-06, yappang의 노트북 Claude. 이 문서는 **다른 노트북에서 Q4B(Qwen3-4B) 파인튜닝을 이어받는 Claude**가 읽는다. 이 문서만 읽고 바로 이어서 할 수 있게 썼다. 배경·근거는 `q4b-plan.md`에 있다.

> **2026-11-08 갱신**: 이 문서는 2026-11-06 시점의 인수인계다. 이후 **Q4B 본 학습(`q4b-v1`)은 다른 컴퓨터에서 완료됐다.** 아래 1절의 "아직 안 돌렸다·구성 미확정"과 2~4절의 학습 준비·실행 순서는 당시 기준이므로, 재학습이나 다른 PC 재현이 필요할 때만 참고한다. 학습 결과물은 `train_model_q4b/deploy/q4b-v1/`(GGUF Q8_0, Modelfile, 시험판 README)에 있고, 결과 수치는 그 README를 본다.
> 폴더 이름이 `train_model`에서 `train_model_q4b`로 바뀌었다. 가상환경은 `members/yappang/.venv` 하나를 backend와 함께 쓴다.

## 0. 먼저 지킬 것

- 사용자는 **yappang**(이메일 ttobargy70@gmail.com)이다. 작업 폴더는 `members/yappang/`이고, 코드·문서 수정은 이 안에서만 한다. 다른 팀원 폴더(`members/byungjun`, `haechan`, `hyeonkyeong`)와 공용 파일(`docs/`, `docs/interface.md`)은 **읽기만** 한다.
- 루트 `CLAUDE.md`의 팀 규칙을 따른다: 커밋 메시지는 `[yappang] 한 일`, force push 금지, push 전 `git pull`, 자기 폴더 파일만 커밋, `.env`와 대용량 파일(데이터·모델 가중치)은 커밋하지 않는다.
- 문서 요청은 `members/yappang/docs/`에 한국어, 영문 소문자·하이픈 파일명으로 저장한다.
- **사용자가 시작하라고 말하기 전에는 본 학습을 시작하지 않는다.** 환경 확인·dry-run·짧은 스모크 테스트까지는 해도 된다.
- 8B(팀 공동) 트랙과 Q4B(yappang 단독) 트랙은 별개다. 이름에 8B/Q4B를 구분해 쓴다. 8B 결과를 읽고 비교하는 것만 하고, 8B 학습·변환 작업은 하지 않는다.

## 1. 지금까지의 상태 (2026-11-06)

| 항목 | 상태 |
|---|---|
| 목표 | Qwen3-4B를 QLoRA로 파인튜닝해 "자연어 투자 원칙 → 지표 20개 JSON" 변환기(시연용)를 만든다. 결과물 이름 `q4b-v1` |
| 스크립트 | `members/yappang/train_model_q4b/scripts/`에 있고 **커밋됨**(`edb8724`). 원래 노트북(RTX 4060 8GB)에서 동작 확인 |
| 스모크 테스트(원래 노트북) | 20스텝 8분, 스텝당 19초, VRAM 7.9/8.2GB, OOM 없음, loss 0.74→0.36 |
| 학습 전 기준선 | `--tag base`: JSON 99.1%, 형태 0%, 필드 0/80, 은어 0/14, 완전일치 0% (원래 노트북의 `outputs/eval_base.jsonl`, 저장소에는 없음) |
| 본 학습 | ~~아직 한 번도 안 돌렸다~~ → **완료(2026-11-08 기준). 다른 컴퓨터에서 학습했다** |
| 학습 구성 | ~~미확정~~ → 당시 권장안은 A(전체 데이터, 에폭 2, 약 3.8시간@4060)였다. 실제로 쓴 구성과 학습 시간은 이 문서에 기록돼 있지 않다 |

## 2. 이 노트북에서 준비하기

저장소에 없는 것(gitignore): `.venv`, `outputs/`, `data/*.jsonl`. 아래를 순서대로 만든다.

1. `git pull`로 최신을 받는다. `train_model_q4b/scripts/`, `requirements.lock.txt`가 있어야 한다.
2. **GPU 확인**: `nvidia-smi`로 GPU 이름·VRAM을 확인하고 **사용자에게 알려 준다**. VRAM이 8GB 이하면 배치 1 x 누적 16, 그 이상이면 3절의 조정안을 쓴다. 다른 프로세스(Ollama 등)가 GPU를 쓰고 있으면 끈다.
3. **가상환경**: 파이썬 3.12(3.10~3.12) venv를 `members/yappang/.venv`에 만든다(backend와 train_model_q4b가 함께 쓴다). `pip install --extra-index-url https://download.pytorch.org/whl/cu128 -r train_model_q4b/requirements.lock.txt -r backend/requirements.txt`로 설치한다. `torch==2.11.0+cu128`은 PyPI에 없어서 PyTorch 인덱스 옵션이 꼭 필요하다(검증된 버전: torch 2.11+cu128, transformers 5.22.1, peft 0.21.2, trl 1.17.1, bitsandbytes 0.50.2). CUDA 버전이 다르면 torch 휠만 맞는 것으로 바꾼다. Windows면 bitsandbytes 호환을 먼저 확인한다(원래 환경은 WSL2 Linux).
4. **데이터**: `members/byungjun/finetune_merged/train.jsonl`, `val.jsonl`을 `members/yappang/train_model_q4b/data/`로 복사한다(이 폴더의 `*.jsonl`은 gitignore). 복사 후 해시를 확인한다.

   ```
   sha256sum train_model_q4b/data/train.jsonl train_model_q4b/data/val.jsonl
   ce61af6138fd7d37f3ab0732983c7d3bbd2a97eb89a032b405f7c743cb513cb5  train.jsonl
   9bf91d786df02cac9e17ed36b6887699d99c454a70631e29e2b4f037805c07ce  val.jsonl
   ```
   해시가 다르면 **멈추고 사용자에게 알린다**(병준이 병합본을 갱신했을 수 있다). 행 수는 train 5,202 / val 275여야 한다.

   > **2026-11-08 갱신**: 위는 **원본(original)** 기준이다. 학습은 부등호·조사 오류를 고친 수정본(`train_fixed.jsonl` 5,175 / `val_fixed.jsonl` 270)으로 하고, 학습 스크립트의 기본값이 수정본이다. 원본은 `data/backup/`에 있다. 현재 파일·해시·변경 이력은 `train_model_q4b/data/DATA_VERSION.md`가 기준이다.
5. **평가셋**: `members/hyeonkyeong/data/eval_1-7.jsonl`, `eval_8-13.jsonl`, `eval_14-20.jsonl`(111문항, 저장소에 있음). `eval_q4b.py`가 상대 경로로 읽으므로 저장소 구조를 바꾸지 않는다.
6. **모델**: `Qwen/Qwen3-4B`(약 8GB)는 첫 실행에서 Hugging Face가 자동으로 받는다. 디스크 여유 25GB 이상을 확인한다.

## 3. 실행 순서

항상 `members/yappang/train_model_q4b/`에서 실행한다. 파이썬은 `../.venv`(`members/yappang/.venv`)의 것을 쓰고 `-I -X utf8`을 붙인다.

1. **dry-run** (GPU 불필요, 모델 가중치 불필요, 토크나이저만 받음)
   ```
   ../.venv/bin/python -I -X utf8 scripts/train_qlora.py --dry-run
   ```
   기대(기본값=수정본): 학습 샘플 **5,600개**(val 294개), 마지막 줄 `정답이 <|im_end|> 로 끝나는 샘플: 5600/5600`. 맨 앞에 `[데이터] train: …train_fixed.jsonl (5175대화, sha256 e50fa8ad7e6c…)`가 나와야 한다(원본 기준은 5,627개). 다르면 멈추고 알린다. 출력되는 마스크 샘플에서 질문 부분은 마스킹되고 `{"indicators"...}` 같은 답과 `<|im_end|>`만 학습 대상인지 눈으로 확인한다.
2. **스모크 테스트**(약 8분@4060): `... scripts/train_qlora.py --max-steps 20 --out outputs/smoke`
   스텝당 시간과 최대 VRAM(`nvidia-smi`)을 기록한다. 이 값으로 전체 시간을 다시 계산한다(스텝 수 ≈ 에폭 x 351). 원래 노트북의 19초/스텝과 비교해 사용자에게 알린다.
3. **구성 확인 후 본 학습** (사용자가 시작하라고 한 뒤에만). 에폭은 **처음부터** 지정한다(코사인 스케줄이 `--epochs` 기준이라 중간에 멈추면 학습률이 덜 줄어든다).
   ```
   nohup ../.venv/bin/python -I -X utf8 scripts/train_qlora.py --epochs 2 --out outputs/q4b-v1 > train_q4b.log 2>&1 &
   ```
   - 8GB 기준 기본값: `--batch 1 --accum 16`, `--max-len 1280`, lr 1e-4, r32/alpha 64. 유효 배치 16을 유지한다.
   - VRAM 16GB 이상이면 `--batch 2 --accum 8` 등을 스모크로 먼저 확인한다. OOM이 나면 `--batch 1 --accum 16`으로 돌아간다.
   - 0.5에폭마다 평가·저장하고 `load_best_model_at_end`로 val loss가 최저인 체크포인트를 고른다. 진행은 `tail -f train_q4b.log`로 본다.
   - 학습 중 절전·로그아웃을 막고 다른 GPU 작업을 하지 않는다.
   - `--resume` 옵션은 이 스크립트에 **없다**(확인 못 함). 중단되면 마지막 체크포인트가 `outputs/q4b-v1/checkpoint-*`에 남지만, 이어서 학습하는 기능은 필요 시 추가해야 한다.
4. **평가** (학습 후)
   ```
   ../.venv/bin/python -I -X utf8 scripts/eval_q4b.py --adapter outputs/q4b-v1 --tag q4b-v1
   ```
   결과는 `outputs/eval_q4b-v1.jsonl`과 터미널 요약이다. `max_new_tokens`는 **900 유지**(정답 최대 620토큰이라 충분). 학습 전 기준선이 필요하면 `--tag base`도 같은 조건으로 돌린다(어댑터 없이).

## 4. 학습 구성 결정 (사용자에게 물어볼 것)

| 구성 | 데이터 | 에폭 | 시간(4060 기준) |
|---|---|---|---|
| A (기본 권장) | 전체 5,202대화 | 2 | 약 3.8시간 |
| D | 전체에서 S4를 하위 유형별로 절반(665→약 330), S1 되묻기를 절반(1,326→약 660)으로 층화 추출 | 2 | 약 3.0시간 |

- D를 택하면 `data/train_sub.jsonl`을 **따로 만든다**(시드 고정, 원본 보존, 유형별 건수를 사용자에게 보여 준 뒤 학습). `train_meta.jsonl`의 `type`/`kind`로 유형을 구분한다. 학습 때 `--train data/train_sub.jsonl`을 쓴다.
- 이 노트북의 GPU가 4060보다 빠르면 시간은 그에 맞게 줄어든다. 스모크 결과로 재계산해서 알린다.

## 5. 평가 기준 (Q4B 자체 기준, 팀과 별개로 정해도 된다는 합의)

| 지표 | 정의 | 목표 |
|---|---|---|
| JSON 유효율 | 출력이 JSON으로 파싱되는 비율 | 99% |
| 필드 정확도 | 정답의 `source=user` 지표의 id·operator·value·unit 전부 일치 | 90% |
| 은어 변환율 | kind에 별칭·오타·구어가 든 문항의 완전일치율 | 90% |
| 형태 일치율, 완전일치율 | 최상위 키 집합 일치 / 파싱 결과가 정답과 완전 일치 | 참고 |

- 8B 쪽 수치와 **정의가 다르다.** haechan의 "필드 정확도"(default 지표 포함, 필드 단위)는 후하게 나온다(v3 시험 91.1%). 비교하려면 haechan의 "사용자 지정 지표 정확도"(v3 시험 16.2%, 병준 v1 35.0%)와 본다. 결과를 보고할 때 어느 정의인지 항상 적는다.
- **유형별 오답 분포를 반드시 확인한다**(정답 유형 → 모델이 고른 유형: 추출/되묻기/거절). 8B v1·v2는 평균 loss가 낮아도 한 유형으로 쏠렸다(원인은 `group_by_length=True`였고, 우리 스크립트에는 없다). 쏠림이 보이면 학습 코드를 먼저 의심한다.
- 평가셋 111문항: 추출 67 / 되묻기 30 / 거절 14. 학습 데이터와 겹치는 문장은 0건이다.
- S3·S4·S6·S7은 평가셋에 없다. 이 유형은 점수로 확인되지 않으므로 val의 해당 샘플로 따로 본다.

## 6. 아직 하지 않은 것·주의

- **GGUF 변환·Ollama 등록·`LLM_PROVIDER=local` 연동**: 학습 후 단계이고 변환 스크립트는 아직 없다. 어댑터를 병합한 뒤 GGUF Q4로 변환하고 Ollama에 `q4b`로 등록하는 순서다(Ollama의 템플릿·system 문구가 학습 때와 글자 그대로 같아야 한다). 이 단계는 원래 노트북(앱이 도는 PC)에서 하는 것이 자연스러우므로 사용자와 위치를 먼저 정한다.
- 어댑터 가중치(`adapter_model.safetensors`, 수백 MB)와 `outputs/`는 **커밋하지 않는다.** 원래 노트북으로 옮길 때는 사용자와 방법(USB, 클라우드 등)을 정한다.
- 이 폴더에서 `train_model_q4b/byungjun_ref/`는 원래 노트북에만 있는 병준 자료 복사본이라 저장소에 없다. 필요하면 `members/byungjun/finetune_train/`을 직접 읽는다.
- 8B v3 본 학습은 haechan이 진행 중이다. 결과는 `members/haechan/finetune/results/RESULTS.md`에서 읽을 수 있다.
- 원래 노트북에는 학습과 무관한 백엔드·프론트 작업도 있다(`backend/.env`의 `EXTERNAL_MODE=live` 등). 이 노트북의 작업과 섞지 않는다.

## 7. 끝나면 사용자에게 보고할 것

1. 사용한 GPU, 실제 스텝당 시간, 총 학습 시간, 최종 선택된 체크포인트와 val loss
2. 5절 지표 5개 + kind별 완전일치율 + **유형별 오답 분포**
3. 기준선(base)과 비교, 가능하면 8B와의 비교(정의 명시)
4. 사용한 학습 구성(A/D, 에폭, batch/accum)과 학습 로그 위치
5. 결과 요약을 `members/yappang/docs/`에 한국어 문서로 저장하고 `[yappang]` 형식으로 커밋(가중치 제외). push는 사용자 확인을 받는다.

## 8. 관련 문서

| 파일 | 내용 |
|---|---|
| `members/yappang/docs/q4b-plan.md` | Q4B 계획·근거·점검 결과 |
| `members/yappang/docs/finetune-procedure.md` | 팀 8B 절차와 현황 |
| `members/haechan/finetune/results/RESULTS.md` | 8B v1~v3 결과, `group_by_length` 원인 |
| `members/hyeonkyeong/finetune_v1.0/REVIEW.md` | 8B v1 리뷰(데이터 유형 비율 문제) |
| `members/byungjun/finetune_merged/` | 학습 데이터 원본 |
