# 학습 데이터 버전 (Q4B)

> **2026-11-09 갱신: 최종 통합본 fixed-4 (8B·4B 공용, 팀 합의).** 파일: `train_fixed4.jsonl`(6,942대화), `val_fixed4.jsonl`(314대화), `*_meta_fixed4.jsonl`. 해시는 `SHA256SUMS_data.txt`·`../../data/train_data/v4_report.json`.
> 학습 스크립트 `scripts/train_qlora.py`의 `TRAIN_FILE`/`VAL_FILE`/`RUN_NAME` 기본값은 **아직 fixed-3/q4b-v3**다. v4를 돌릴 때 `--train data/train_fixed4.jsonl --val data/val_fixed4.jsonl --out outputs/q4b-v4`로 지정한다(학습은 사용자가 시작하라고 할 때만).

> **파일 정리 (2026-11-09):** 이 폴더에는 fixed-4 최종본 4개, 통합 시험 세트 `test_set.jsonl`(+`TEST_SET.md`), 이 문서, `SHA256SUMS_data.txt`만 둔다. 이전 버전(원본·fixed-1~3, 메타, 병합 백업, 외부 LLM 450건, 이전 평가 111문항 보관본, 점검 CSV)은 모두 `backup/2026-11-09/`로 옮겼고(해시 전부 일치 확인) 이전 해시 목록은 그 안의 `SHA256SUMS_data_before.txt`에 있다. 아래 표의 fixed-1~3·원본 파일 이름은 그 폴더 안에서 찾는다. 시험 문장은 `test_set.jsonl`(이 폴더, 설명 `TEST_SET.md`) 하나로 합쳤다.

## 현재 버전: fixed-4 (2026-11-09)
fixed-3(우리 수정 규칙·label 키 적용) + haechan `data_v6` 반영. 생성 코드 `../../data/scripts/build_v4_data.py`, 변경 목록 `../../data/train_data/v4_changes.csv`, 제외 목록 `v4_dropped.csv`.

| 단계 | 내용 | 건수 |
|---|---|---|
| 되묻기 유형 교체 | v6와 reason이 반대인 문장을 v6 정답으로 교체(B4 저점 반등, B6 연속 배당, "규모" 큰/작은=14·19 등) | 33문장 |
| v6 전용 추가 | v6에만 있는 문장 추가(후보 키 name→label) | 433 |
| 제외 | `data_fixes.py`의 의미 반전·깨진 문장(v6 train 25 + v6 val 5) | 30 |
| val | v6 val(+규칙 적용) 314. 우리 val에만 있던 문장은 train으로 이동 | 70 이동 |

응답 분포(train): 추출 3,144 / 거절 539 / 값 되묻기 1,700 / 지표 모호 1,313 / 기간 72 / 용어 설명 599. 평가 문장과 같은 문장 0건, train·val 겹침 0건, `<|im_end|>` 종료 샘플 7,367/7,367(dry-run).
"규모가 큰/작은"류 7문장은 모두 지표 모호(14·19)로 통일됐다.

---


**지금 학습에 쓰는 파일: `train_fixed3.jsonl`, `val_fixed3.jsonl`** (학습 스크립트 `scripts/train_qlora.py`의 `TRAIN_FILE`, `VAL_FILE` 기본값, 다음 학습 이름 `RUN_NAME = q4b-v3`)

## 현재 버전: fixed-3 (2026-11-08, q4b-v3용)

| 파일 | 대화 수 | 학습 샘플 수 | sha256 |
|---|---|---|---|
| `train_fixed3.jsonl` | 6,439 | 6,864 | `cab1c4c9e2a62139bf1adfc8ff9f8bd4c1a9c9cc2504546756413b9c86794cc6` |
| `val_fixed3.jsonl` | 337 | | `0c35ef7ce27d149a0d9a99682aaf0aeb475769f0cbd821e5408373e5a33d4841` |
| `train_meta_fixed3.jsonl` | 6,439 | | `0e150d0c3da53844d91a9bbd4d43419890867b38600f1414aa205f1176f141a1` |
| `val_meta_fixed3.jsonl` | 337 | | `6b542f7d6cea9b99089d9c81b386a3445795181d60938182f669ef758e2ca859` |

fixed-3 = fixed-2 + 외부 LLM이 만든 "지표 모호" 되묻기 문장 449건(`stock_ambiguous_450.jsonl` 450줄 중 평가 개념어 1건 제외). 반영 코드는 `data/scripts/add_external_amb.py`(members/yappang 기준), 내역은 `data/train_data/v3_external_report.json`, 버린 문장은 `v3_external_rejected.csv`. 정답(후보·메시지)은 코드가 그룹 표(G1~G18)로 만들었고, LLM의 `keyword`는 메타에만 남겼다. 형식·숫자·지표 이름·금지어·추천 표현·평가 문장·기존 문장·자체 중복을 검사했고 449건이 모두 통과했다. 이 문장들은 수동으로 훑어보았을 뿐 전수 검수는 하지 않았다.

**모호 되묻기 비중**: fixed-1 약 430건 → fixed-2 약 750건 → fixed-3 **1,176건**(값 되묻기 1,335건과 거의 같음). 한 지표가 분명한 문장까지 지표를 되묻는 부작용이 생길 수 있으므로, v3 평가에서 "되묻기(값 없음)"(v2 17/18)과 단일 지표 유형이 떨어지지 않는지 함께 본다.

## 이전 버전: fixed-2 (학습에 쓰지 않음, fixed-3의 바탕)

| 파일 | 대화 수 | 학습 샘플 수 | sha256 |
|---|---|---|---|
| `train_fixed2.jsonl` | 6,013 | 6,438 | `81328714674bf5dbd85931a1672670dcc7b1234b5b3d0e4dfbe1fe93e010ae0a` |
| `val_fixed2.jsonl` | 314 | | `6be9c7a66a1dd1ce0cb4b86e4a42c5b4b7f8501cc269bdf321fe8c6d4576d23d` |
| `train_meta_fixed2.jsonl` | 6,013 | | `6736aaadc0f903bd04076c876916e34076612e3b9a5f47993844274b815b7140` |
| `val_meta_fixed2.jsonl` | 314 | | `400fc3931e5140a896004cfaf7377774353f020bc49b0f2415aa28bc7c8e1b31` |

fixed-2 = fixed-1 + (1) 되묻기 후보 키 통일 + (2) 평가에서 약했던 유형의 보강 882건. 생성 코드는 `data/scripts/build_v3_data.py`(members/yappang 기준), 결과와 내역은 `data/train_data/`의 `v3_report.json`, `v3_additions_preview.csv`(추가 문장 전체), `v3_conflict_audit.csv`(사람이 볼 충돌 목록).

| 바꾼 것 | 내용 |
|---|---|
| 후보 키 통일 | 되묻기 `candidates`의 `{"id","name"}` 376대화를 `{"id","label"}`로 바꿈(평가 정답 형식, 백엔드는 둘 다 읽음). `area` 후보는 그대로 |
| 단일 지표 260건 | 부채비율·차입금의존도, 매출·영업이익 증가율, 영업이익·매출순이익률 등 번호 혼동이 보인 지표를 더 많이 |
| 복수 지표 140건 | 같은 값이 반복되는 문장("A와 B 모두 20% 이상"), 3개짜리 포함 |
| 지표 모호 되묻기 420건 | 새 표현 × 6개 틀. 메시지는 문장의 말을 따라 쓴다(안전하다고/싸다고/성장…) |
| 거절 62건 | 약어 없는 서술형 "20개 밖"(14개 개념), 매매 시점·종목 추천 변형 |

- 평가 문장(`eval_set.jsonl`, `H5-*.jsonl`)과 같은 문장, 평가에 나온 개념어(현금 보유, 배당 성장, EPS, ROA, ROIC, PEG, MACD, 기관, 가성비, 튼튼, 잘 버는, 롤러코스터 등)는 보강에 쓰지 않았다. 평가가 암기로 올라가지 않게 하기 위해서다.
- 추가분은 템플릿으로 만들어 표현 다양성이 제한적이다. 모호 되묻기 420건은 같은 틀 6개를 돌려 썼다. 효과가 부족하면 외부 LLM으로 표현을 늘린다.
- 되묻기 충돌 점검 결과(`v3_conflict_audit.csv`): 같은 표현이 한쪽은 지표 되묻기, 다른 쪽은 값 되묻기로 학습된 것이 6개 표현에서 나왔고, 같은 문장에 정답이 갈리는 경우는 없었다. 건수가 적어 자동으로 고치지 않았다(사람 판단 대상).

학습을 시작하면 쓴 파일의 경로·대화 수·sha256이 터미널에 출력되고, 출력 폴더(`outputs/<이름>/data_used.json`)에도 남는다. 어떤 데이터로 학습한 모델인지는 이 파일로 확인한다.

## 모델 버전과 데이터 대응 (이름이 겹치지 않게)

| 모델 | 학습 데이터 | 어댑터 폴더 | 변환·배포 이름 | 상태 |
|---|---|---|---|---|
| `q4b-v1` | original (train.jsonl 5,202대화) | `outputs/q4b-v1` (다른 PC에서 학습) | `deploy/q4b-v1`, `stockrule-q4b-v1.Q8_0.gguf`, Ollama `qwen3-4b-stockrule` | 완료·시험판 |
| `q4b-v2` | fixed-1 (train_fixed.jsonl 5,175대화) | `outputs/q4b-v2` | `deploy/q4b-v2`, `stockrule-q4b-v2.Q8_0.gguf`, Ollama `qwen3-4b-stockrule-v2` | 학습 완료(2026-11-08, 에폭 3, RTX 3070 Ti 8GB, 5시간 11분, eval_loss 0.0093). 평가 111문항 완전 일치 63.1%, 필드 정확도 78.8%(`outputs/eval_q4b-v2.jsonl`). 병합·GGUF 변환은 아직 |
| `q4b-v3` | fixed-3 (train_fixed3.jsonl 6,439대화) | `outputs/q4b-v3` | `deploy/q4b-v3`, `stockrule-q4b-v3.Q8_0.gguf`, Ollama `qwen3-4b-stockrule-v3` | 데이터 준비 완료, 학습 전(원격 WSL RTX 5080에서 학습 예정) |

- 같은 모델의 파일은 이름 끝을 같은 `v번호`로 맞춘다: 어댑터 `outputs/q4b-v2`, 병합 `outputs/q4b-v2-merged-nf4`, 평가 결과 `outputs/eval_q4b-v2.jsonl`(`--tag q4b-v2`), 학습 로그 `train_q4b_v2.log`.
- 데이터를 바꿔 다시 학습하면 번호를 올린다(`q4b-v3`…). `scripts/train_qlora.py` 맨 위의 `RUN_NAME`이 `--out`의 기본값이다.
- 학습 스크립트는 `outputs/<이름>`에 이미 어댑터(`adapter_model*`)나 체크포인트가 있으면 멈춘다. 이전 학습을 덮어쓰지 않기 위해서다.
- 학습한 모델이 어떤 데이터를 썼는지는 `outputs/<이름>/data_used.json`(파일 경로·대화 수·sha256)으로 확인한다.

## 이전 버전: fixed-1 (q4b-v2 학습에 사용)

`train_fixed.jsonl`(5,175대화 / 5,600샘플, sha256 `e50fa8ad…da07`), `val_fixed.jsonl`(270대화, `c39ee31829ef…`), `*_meta_fixed.jsonl`. **지우지 않는다.** q4b-v2가 이 파일로 학습했다.

## 이전 버전: original (백업)

`backup/` 폴더에 보관. **학습에 쓰지 않는다.** 병준 최종 병합본과 같은 파일이다.

| 파일 | 대화 수 | 학습 샘플 수 | sha256 |
|---|---|---|---|
| `backup/train.jsonl` (= `train.jsonl`) | 5,202 | 5,627 | `ce61af6138fd7d37f3ab0732983c7d3bbd2a97eb89a032b405f7c743cb513cb5` |
| `backup/val.jsonl` (= `val.jsonl`) | 275 | | `9bf91d786df02cac9e17ed36b6887699d99c454a70631e29e2b4f037805c07ce` |

`data/train.jsonl`, `val.jsonl`, `*_meta.jsonl`(`_fixed` 없는 것)은 수정 전 원본이라 그대로 남겨 두었다. 기본값으로는 읽히지 않는다.

## fixed-1에서 바꾼 것

원본 대비 train 124건 수정·27건 제외, val 3건 수정·5건 제외. 건별 내역은 `fix_log.csv`, 점검에서 나온 의심 목록은 `train_audit_issues.csv`.

- **수정**: 정답의 부등호 경계 오류(`미만`→`<`, `넘는`→`>`, `이상`→`>=`, `~를 넘지 않는`→`<=` 등)와 안내 문구의 조사 오류(`배당성향는`→`배당성향은`). 수정한 대화는 `*_meta_fixed.jsonl`의 `_fix` 항목에 내용이 적혀 있다.
- **제외**: 제외 문장인데 포함 조건으로 반전된 것, 문장이 깨진 것, 방향 해석이 모호한 것(지표 16·17).
- **고치지 않은 것**: 지표 매핑의 의미 오류, S1/S2 정답 충돌(같은 표현이 단일 지표와 되묻기로 갈린 것), S6·S7 설명 문구 내용. 사람이 판단해야 한다.

## 데이터를 바꿔 다시 학습할 때 (혼선 방지 규칙)

1. 새 데이터는 **파일명에 구분자를 붙여** 만든다(예: `train_fixed2.jsonl`, `val_fixed2.jsonl`). 이전 파일은 덮어쓰지 말고 `backup/`에 둔다.
2. `scripts/train_qlora.py` 맨 위의 `TRAIN_FILE`, `VAL_FILE`을 새 파일명으로 바꾼다. 이 두 상수가 유일한 기본값이다.
3. 이 문서의 "현재 버전" 표(파일명·대화 수·샘플 수·sha256)를 갱신하고, 이전 버전을 "이전 버전" 절로 내린다. 해시는 `sha256sum <파일>`로 구한다.
4. `--dry-run`으로 샘플 수와 `정답이 <|im_end|> 로 끝나는 샘플`이 전부인지 확인한 뒤 학습한다.
5. `scripts/merge_train_sets.py`는 기본으로 수정 규칙을 적용해 `_fixed` 이름으로 쓴다(2026-11-08 변경). `--no-fix`를 주면 수정이 빠진 원본 이름(`train.jsonl`)으로 쓰니, 학습용으로는 쓰지 않는다. 병합을 다시 하면 새 파일을 위 규칙대로 구분되는 이름으로 저장하고 DATA_VERSION.md를 갱신한다.
6. 인수인계 문서(`docs/q4b-handoff.md`, `docs/q4b-plan.md`)의 기대 샘플 수·해시도 함께 갱신한다.

## 학습용 데이터를 만드는 코드

학습 데이터 생성과 수정은 코드로 재현할 수 있다. 8B(팀)와 Q4B가 같은 결과를 쓴다.

| 단계 | 코드 | 하는 일 |
|---|---|---|
| ① S1·S2 문장 조립 | `data/gen_prompts/assemble_s1_s2.py` | 로컬 모델 출력 → 정답 포함 샘플. **2026-11-08부터 문장의 부등호 말과 정답 연산자를 대조한다**(전에는 S2가 기본 연산자로 정답을 만들어 어긋남이 생겼다) |
| ② 병합 | `train_model_q4b/scripts/merge_train_sets.py` | 유형별 파일을 합쳐 train/val로 나눈 뒤 ③ 수정 규칙을 적용하고 `_fixed` 이름으로 쓴다(팀원 폴더의 원본 파일이 필요). 수정 없이 원본 결과가 필요하면 `--no-fix`. 예전 `merge_train_data.py`는 구버전이라 쓰지 않는다 |
| ③ 수정 규칙 적용 | `data/scripts/data_fixes.py` + `data_fixes_rules.json` | 부등호 경계·조사 수정, 반전·깨진 문장 제외. 입력 문장 기준이라 병합 순서가 달라도 같게 적용된다 |
| ④ 학습용 파일 생성 | `data/scripts/build_train_data.py` | ②의 결과(또는 병합 완료본)에 ③을 적용해 `data/train_data/`에 쓴다 |

```
cd members/yappang
python -I -X utf8 data/scripts/build_train_data.py
```

- 팀원 폴더의 원본이 있으면 ②를 새로 돌리고, 없으면(이 PC) 병합 완료본 `train_model_q4b/data/backup`을 쓴다. 입력은 `--from-merged`로 고른다.
- 병합 코드(②)의 수정 로직은 보관본으로 시험했다. 보관본에 적용한 결과가 기존 `*_fixed`와 완전히 같다. 다만 팀원 원본을 읽어 새로 병합하는 경로 자체는 이 PC에 원본이 없어 아직 실행해 보지 못했다.
- 결과 `data/train_data/{train,val}_fixed.jsonl`, `*_meta_fixed.jsonl`은 `train_model_q4b/data/*_fixed.jsonl`과 **해시까지 같다**(실행하면 동일 여부를 출력한다). 두 위치는 같은 내용의 사본이다.
- `data/train_data/build_report.json`에 입력 파일 해시, 줄 수, 조치 건수, 검사 결과가 남는다. 건별 내역은 `fix_log.csv`.
- 수정 규칙을 늘릴 때는 `data_fixes_rules.json`에 입력 문장을 추가한다(`drop_texts`: 제외, `neg_fix`: 부정 표현의 연산자, `explicit`: 지표별 연산자 지정).
- 오류 유형이 새로 나오면 ①(조립 단계 검사)에서 먼저 막고, ③에는 사람이 판단한 예외만 둔다.
