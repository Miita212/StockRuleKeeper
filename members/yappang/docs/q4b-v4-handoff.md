# Q4B v4 인수인계 (2026-11-09 작성, 작성: yappang의 Claude)

이 문서는 **다른 컴퓨터에서 이 작업을 이어받는 사람과 Claude**가 가장 먼저 읽는다. 압축을 푼 `yappang/` 폴더는 저장소의 `members/yappang/`와 같은 구조다.

## 0. 먼저 지킬 것
- 사용자는 **yappang**(한글 "얍팡"도 같은 사람)이다. 작업은 이 `yappang/` 폴더 안에서만 한다. 다른 팀원 폴더는 읽기만 한다.
- 저장소에 올릴 때: 커밋 메시지 `[yappang] 한 일`, force push 금지, push 전 `git pull`, `.env`·데이터·모델 가중치는 커밋하지 않는다(`train_model_q4b/.gitignore` 참고).
- **사용자가 시작하라고 하기 전에는 본 학습을 시작하지 않는다.** 추천·의견 요청에는 실행하지 말고 대화로 먼저 보여준다.
- 수치를 보고할 때는 측정값과 추정을 구분한다.

## 1. 지금까지 한 일
| 버전 | 내용 | 결과 |
|---|---|---|
| v1 | 원본 병합 데이터, Qwen3-4B QLoRA | 필드 63.7%, 완전일치 54.1% |
| v2 | 부등호·조사 오류를 고친 fixed 데이터 | 필드 78.8%, 완전일치 63.1% |
| **v3** | fixed-3 (v2 + 보강 882건 + 외부 LLM "지표 모호" 449건, 6,439대화) | **필드 90.0%(목표 달성)**, 은어 85.7%, 완전일치 65.8%(73/111) |

v3 상세는 `train_model_q4b/q4b-v3-result/REPORT.md`(원격 PC의 Claude가 쓴 보고서)에 있다. 학습은 RTX 5080 16GB(WSL2)에서 2시간 6분, 오류 없음. 이전 세션의 **대화 기록은 이 압축 파일에 없다.** 기록은 REPORT.md와 로그가 전부다.

## 2. 다음에 할 일 → `docs/q4b-v4-plan.md`
핵심만 적는다. 근거와 문항 목록은 그 문서에 있다.
1. v3 오답 38건 중 **11건이 값 되묻기와 지표 되묻기의 혼동**이다. 지표 모호 되묻기 데이터를 430 → 1,176건으로 늘린 부작용으로 보인다(**가설, 데이터 확인 전**).
2. **평가 정답의 거절 문구에 문법 오류**가 있어("매출순이익률나", "EPS 증가율는") 거절 8건이 구조는 맞아도 틀린 것으로 채점된다.
3. 제안 순서: ① 구조 일치율 지표 추가 후 v2·v3 재채점(학습 불필요) → ② 학습 데이터의 충돌 표현·거절 문구 조사 오류·`known` 키 점검 → ③ fixed-4 데이터 작성 → ④ v4 학습 → ⑤ 필요 시 모호 비중 조절 실험.
4. 아직 사용자에게 승인받은 것은 **개선안 작성까지**다. 1단계부터 진행해도 되는지 사용자에게 먼저 묻는다.

## 3. 압축 파일 내용
```
HANDOFF.md                         이 문서
docs/                              q4b-v4-plan.md(다음 계획), q4b-plan.md, q4b-handoff.md(11/06 이전 인수인계),
                                   finetune-procedure.md, eval-errors-v3-2ep.md, model-improvement-plan.md,
                                   team-adapter-apply.md, 3에폭 결과.md, interface.md
data/                              members/yappang/data 전체: 지표 마스터(H1), 동의어(H2), 되묻기 옵션(H3), 시드(H4),
                                   평가(H5), 검수(H7), 합성 생성물(S-*, gen_*), backup/
data/scripts/                      build_v3_data.py, add_external_amb.py 등 데이터 생성 코드(fixed-4도 이 구조로 만든다)
data/train_data/                   fixed-1/2/3 train·val·meta 전부, v3_*.json/csv 보고서(충돌 점검 등)
train_model_q4b/
  scripts/                         train_qlora.py, eval_q4b.py, merge_adapter.py, eval_ollama.py 등
  requirements(.lock).txt
  data/                            train_model_q4b/data 전체: 원본 train/val, fixed-1/2/3, 메타, backup/, own_merge_backup/,
                                   eval_set.jsonl(111문항), stock_ambiguous_450.jsonl, DATA_VERSION.md, SHA256SUMS_data.txt
                                   (**학습에 쓴 것은 train_fixed3 / val_fixed3**)
  q4b-v3-result/                   REPORT.md, 로그 4개, outputs/eval_q4b-v3.jsonl, outputs/q4b-v3/(어댑터 264MB)
  outputs/                         eval_q4b-v1-gguf.jsonl, eval_q4b-v2.jsonl (v2와 비교용 평가 결과)
  train_q4b_v2.log, eval_q4b_v2.log
  byungjun_ref/                    병준 8B 참고 코드·명세
```

## 4. 이 파일에 **없는 것** (필요하면 따로 가져간다)
| 항목 | 위치(원래 PC) | 필요한 경우 |
|---|---|---|
| v3 병합 모델(8GB), GGUF Q8_0(4.3GB) | 원격 PC(`q4b-v3-remote`)에만 있고 결과 폴더로 옮기지 않았다 | 시연·Ollama 연동 시 |
| v1 GGUF·Modelfile(`deploy/q4b-v1/`, 4GB) | 이 PC `train_model_q4b/deploy/` | v1 시연 |
| v2 어댑터·체크포인트(1.4GB) | 이 PC `train_model_q4b/outputs/q4b-v2/` | v2와 직접 재추론 비교 |
| 팀 공용 코드·백엔드 | git 저장소 | 이 파일만으로 학습·평가는 가능 |
| Qwen3-4B 기본 모델(약 8GB) | Hugging Face에서 첫 실행 때 자동 다운로드 | 학습·평가 |

## 5. 환경 재현
원격 PC에서 성공한 구성(REPORT.md 1절): Python 3.12(uv로 설치), torch 2.11.0+cu128, transformers 5.22.1, peft 0.21.2, bitsandbytes 0.50.2, RTX 5080 16GB. 시스템 Python이 3.14라 쓰지 않았다.
```
python3.12 -m venv .venv   # uv venv라면 `uv pip install pip` 로 pip 추가
.venv/bin/pip install -r train_model_q4b/requirements.lock.txt --extra-index-url https://download.pytorch.org/whl/cu128
python -m bitsandbytes     # SUCCESS 확인
```
디스크 여유 25GB 이상. VRAM 8GB 이하면 `--batch 1 --accum 16`(기본값), 16GB면 배치를 늘려도 되나 v3는 기본값 그대로 돌렸다.

## 6. 확인 절차 (압축을 푼 직후)
```
cd train_model_q4b/data && sha256sum -c SHA256SUMS_data.txt        # 전부 OK 여야 함(최상위 *.jsonl 22개)
cd .. && python -I -X utf8 scripts/train_qlora.py --dry-run          # 기대: train 6439대화 / val 337대화, 정답이 <|im_end|> 로 끝나는 샘플 6864/6864
```
fixed-3 기준 해시: train `cab1c4c9e2a6…`, val `0c35ef7ce27d…`. 다르면 멈추고 사용자에게 알린다.

## 7. 학습·평가 명령
`train_model_q4b/`에서 실행한다. 스크립트 기본값이 fixed-3, `RUN_NAME=q4b-v3`이다. **v4를 돌릴 때는 `--out outputs/q4b-v4`를 지정하고 `TRAIN_FILE`/`VAL_FILE`(또는 `--train/--val`)을 새 데이터로 바꾼다.** 기존 결과를 덮어쓰지 않게 주의한다.
```
python -I -X utf8 scripts/train_qlora.py --dry-run
nohup python -I -X utf8 scripts/train_qlora.py --epochs 3 --out outputs/q4b-v4 > train_q4b_v4.log 2>&1 &
python -I -X utf8 scripts/eval_q4b.py --adapter outputs/q4b-v4 --tag q4b-v4      # → outputs/eval_q4b-v4.jsonl
python -I -X utf8 scripts/merge_adapter.py --nf4 --adapter outputs/q4b-v4 --out outputs/q4b-v4-merged-nf4   # 요청 시에만
```
옵션(기본값): `--epochs 3 --lr 1e-4 --rank 32 --alpha 64 --max-len 1280 --seed 42`. 평가는 greedy, `enable_thinking=False`, `max_new_tokens=900`. v3 학습은 스텝당 약 5.5~5.9초, 1,287스텝이었다. 에폭은 처음부터 정해서 시작한다(코사인 스케줄이 `--epochs` 기준).

## 8. 알려진 주의점
- `eval_q4b.py`는 `data/eval_set.jsonl`을 읽는다. 팀 폴더의 eval 파일에서 복원한 파일이며 지금은 이 파일만 있으면 된다.
- 평가 출력의 정답 문구(거절 메시지)에 조사 오류가 있다. 8B와 공용 111문항이라 **원본은 고치지 말고** 보조 지표를 추가하는 쪽을 권한다.
- 평가 문항·평가에 나온 개념어(ROA, EPS, PEG, 기관, 가성비, 튼튼, 롤러코스터 등)를 학습 보강 데이터에 쓰지 않는다(암기로 점수가 오르는 것을 막기 위함, v3까지 지킨 원칙).
- 평가는 111문항이라 1문항이 0.9%p다. 2~3문항 차이는 노이즈일 수 있다.
- v3는 원격 PC에서 `HF_TOKEN` 없이 돌렸다. HF 다운로드가 느리면 토큰을 설정한다.
- 학습 중 `outputs/`는 gitignore 대상이다. 결과는 폴더째 옮긴다(이번처럼 `q4b-v3-result/`로 모아 압축).

## 9. 아직 확인하지 않은 것
- 학습 데이터의 충돌 표현 실제 건수(v4-plan 2절 가설)
- 학습 데이터 거절 문구의 조사 오류, `known` 키 유무
- 병합 모델·GGUF가 어댑터와 같은 결과를 내는지(v3는 평가하지 않음)
- 백엔드(`LLM_PROVIDER=local`)와 Q4B GGUF의 실제 연동 호출
