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
- 필드: `test_id`(T001~T234), `source`, `orig_id`, `eval_id`/`id`(=orig_id, 기존 평가 스크립트 호환), `kind`, `text`, `output`(정답), `messages`(system+user). 원본 내용은 고치지 않았으나, 공식 111문항의 거절 정답 8건(T033·T034·T067~T070·T108·T109)은 조사 오류("매출순이익률나 영업이익 볼 수", "EPS 증가율는" 등)를 2026-11-09 팀 합의로 고쳤다. 수정 전 파일: backup/2026-11-09/test_set_before_josa.jsonl. 수정 전 점수와 직접 비교하지 말 것.
- **2026-11-10 정답 수정 10건** (fixed-6-hk 표현 기준 G1~G7 합의): T031·T228 잘 버는 → 모호[5,7] / T064·T229·T194 가성비·가격 매력·가격 대비 → 모호[10,11] / T065 이익이 늘어나는 → 영업이익 증가율(9) 값 되묻기 / T106 롤러코스터 → 변동성(18) 값 되묻기 / T107·T193 규모·크기 큰 → 시가총액(14) 값 되묻기 / T197 푹 꺼진 → 모호[15,16]. 앞 9건은 hyeonkyeong 제안(`fixed6-hk-data-2026-11-09/data/test.jsonl`), T194는 같은 기준(G4)이라 yappang이 추가. 수정 전 파일: backup/2026-11-10/test_set_before_g1g7.jsonl, 적용 코드 `data/scripts/apply_test_fixes_20261110.py`. **이 날 이전 점수(v1~v4)와 직접 비교하지 말 것**: 이 10문항은 다시 채점해야 한다(v4 기존 출력을 새 정답으로 다시 채점하면 구조 일치 207→209, 완전 일치 155로 같음).
- 점수는 `source`별로 따로 낸다. 111문항 점수는 예전 수치와 비교하고, haechan 123문항은 새 표현 점검에 쓴다. 합계 234 점수는 참고용이다(문항 수와 난이도가 달라 예전 수치와 직접 비교하지 않는다).
- 생성/재검사(members/yappang 에서): `python3 -I -X utf8 data/scripts/build_test_set.py --haechan <test_haechan 폴더>` (학습 데이터와 겹치면 실패한다).
- 학습 데이터를 바꿀 때마다 이 스크립트로 겹침을 다시 확인한다. 시험 문장을 추가하려면 이 파일 한 곳에만 추가한다.
- Q4B 평가: `python -I -X utf8 scripts/eval_q4b.py --adapter … --tag … [--set official111|haechan|all]` (기본 official111). Ollama도 `eval_ollama.py --set …`.
- 예전 `eval_set.jsonl`은 `backup/2026-11-09/`로 옮겼다(official111과 같은 문장). 앞으로는 `test_set.jsonl`을 쓴다.
