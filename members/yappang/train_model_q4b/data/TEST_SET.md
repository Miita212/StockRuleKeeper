# 통합 시험 세트 (data/test_set.jsonl)

위치: `train_model_q4b/data/test_set.jsonl`, 생성 코드 `data/scripts/build_test_set.py`. 이 파일은 gitignore(`data/*.jsonl`) 대상이라 올릴 때 `git add -f`가 필요하다.

8B·4B가 **같은 시험 문장 하나**를 쓰기 위한 파일이다. 학습(train)·검증(val)에 쓰지 않는다. 만든 날 2026-11-09, yappang.

| source | 문항 | 원본 | 용도 |
|---|---|---|---|
| official111 | 111 | `members/hyeonkyeong/data/eval_1-7·8-13·14-20.jsonl` (id `H5a-…`) | 이전 버전과 같은 기준으로 비교(v1~v7, 8B·4B) |
| haechan58 | 58 | `members/haechan/finetune/test_haechan/test_haechan.jsonl` (id `HT-…`) | 새 표현 일반화 |
| haechan31 | 31 | `test_haechan_v5.jsonl` (id `HT5-…`) | 〃 |
| haechan34 | 34 | `test_haechan_v7.jsonl` (id `HT7-…`) | 〃 |

- 합계 **234문항**. 문장 중복 0, id 중복 0. fixed-4·fixed-3·원본·haechan v6의 train/val과 **동일 문장 0건**(확인함).
- 필드: `test_id`(T001~T234), `source`, `orig_id`, `eval_id`/`id`(=orig_id, 기존 평가 스크립트 호환), `kind`, `text`, `output`(정답), `messages`(system+user). 원본 내용은 고치지 않았다(거절 문구 조사 오류도 그대로).
- 점수는 `source`별로 따로 낸다. 111문항 점수는 예전 수치와 비교하고, haechan 123문항은 새 표현 점검에 쓴다. 합계 234 점수는 참고용이다(문항 수와 난이도가 달라 예전 수치와 직접 비교하지 않는다).
- 생성/재검사(members/yappang 에서): `python3 -I -X utf8 data/scripts/build_test_set.py --haechan <test_haechan 폴더>` (학습 데이터와 겹치면 실패한다).
- 학습 데이터를 바꿀 때마다 이 스크립트로 겹침을 다시 확인한다. 시험 문장을 추가하려면 이 파일 한 곳에만 추가한다.
- Q4B 평가: `python -I -X utf8 scripts/eval_q4b.py --adapter … --tag … [--set official111|haechan|all]` (기본 official111). Ollama도 `eval_ollama.py --set …`.
- 예전 `eval_set.jsonl`은 `backup/2026-11-09/`로 옮겼다(official111과 같은 문장). 앞으로는 `test_set.jsonl`을 쓴다.
