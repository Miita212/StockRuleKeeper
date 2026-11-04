# haechan

## 담당 역할
LLM 담당. 데이터 준비 계획표(`docs/data-preparation-plan(2).xlsx`)의 haechan 담당 8개: H4-a~c(시드), V-1(검증), V-2(분할), T-run(용어 진단), D2·D3(자료 확인).

## 이 폴더가 하는 일

| 작업 | 산출물 | 상태 |
| --- | --- | --- |
| H4-a~c 시드 207개 | `data/seed_1-7.jsonl`(64), `seed_8-13.jsonl`(66), `seed_14-20.jsonl`(77), 만드는 스크립트 `data/build_seed_*.py` | 완료. 팀 합의 전 제안 규칙 포함 |
| V-1 자동 검증 | `data/validate_data.py` + `tests/test_validate_data.py` (47개) | 완료 |
| V-2 분할·평가 격리 | `data/split_data.py` + `tests/test_split_data.py` (24개) | 완료 |
| D2 기관별 용어 자료 | `data/glossary_check.md` | 초안. 확인 못 한 이용조건은 메모에 표시 |
| D3 공개 금융 데이터셋 | `data/public_dataset_check.md` | 초안. KRX-Bench·KFinEval 라이선스 미확인 |
| T-run 용어 진단 | `data/diag_result.md` (예정) | 진행 중 |

**구버전 후보 (쓰지 않음):** 11-04 팀 회의 전에 만든 것이다. 모델이 Qwen2.5 기준이고 형식이 새 계획과 다르다.
`llm/`(지표 20개 코드·출력 검증), `tests/test_schema.py`, `data/build_pilot.py`·`pilot_labels.jsonl`(시범 라벨 33개),
`data/build_dev.py`·`dev_set.jsonl`(dev 113개), `토스_인앱_주의사항.md`(토스 인앱은 제외로 결정됨, 참고용).
삭제하지 않고 남겨 두었다. 새 작업은 위 표의 파일을 쓴다.

## 실행 방법
`members/haechan/` 에서 실행한다 (표준 라이브러리만 사용, 한글이 깨지면 `-X utf8`).
```
# 시드 다시 만들기 (마스터가 바뀌면)
python -X utf8 data/build_seed_1-7.py        # build_seed_8-13.py, build_seed_14-20.py 도 같음

# V-1 검증 (V1~V10)
python -X utf8 data/validate_data.py --master-dir ../byungjun/data --input data/seed_*.jsonl ../hyeonkyeong/data/gen_s3.jsonl \
    --eval ../hyeonkyeong/data/eval_*.jsonl

# V-2 학습/검증/평가 분할 (평가 세트가 그대로 test 가 된다. 분할 사이 겹침이 있으면 종료 코드 1)
python -X utf8 data/split_data.py --pool data/seed_*.jsonl ../hyeonkyeong/data/gen_s3.jsonl ../hyeonkyeong/data/gen_s4_s5.jsonl \
    ../byungjun/data/S-4_gen_s6_s7.jsonl --eval ../hyeonkyeong/data/eval_*.jsonl --master-dir ../byungjun/data --out data/split

# 시험
python -X utf8 tests/test_validate_data.py ; python -X utf8 tests/test_split_data.py
```

## 핵심 함수

| 이름 | 입력 | 출력 | 예시 |
|------|------|------|------|
| `validate_record(rec, master)` (`validate_data.py`) | 샘플 1개, `load_master()` 결과 | 실패 목록 `[(규칙, 메시지)]` (비면 통과) | `validate_record(rec, load_master('../byungjun/data'))` |
| `load_master(dir)` | 마스터 JSON 폴더 | `{지표 id: 마스터 행}` | |
| `run(pool, eval, ratio, master)` (`split_data.py`) | 샘플 목록, 평가 목록 | `(분할, 버린 것, 보고서)` | `run(pool, eval_records)` |
| `group_key(rec)` | 샘플 | 묶음 키 (시드와 그 변형이 같은 값) | `seed_id` 또는 `prompt_id`의 `S1B-` 뒤 |

샘플 형식(한 줄): `{"type": "SEED|S1~S8", "messages": [system, user, assistant], "indicator_ids": [], "seed_id": "", "locked": []}`.
`input`/`output` 형식도 읽는다.

## 필요한 라이브러리
없음 (Python 표준 라이브러리). T-run은 로컬 Ollama(Qwen3-8B)를 쓴다.

## 통합 때 옮길 위치
- `validate_data.py`, `split_data.py`: 학습 데이터를 합치는 단계에서 그대로 사용 (옮길 필요 없음)
- 분할 결과(`data/split/`)는 만들 수 있는 파일이라 커밋하지 않는다 (위 명령으로 다시 만든다)
