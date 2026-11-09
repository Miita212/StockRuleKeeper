# 세션 정리: 2026-11-09 (Q4B v4 평가와 fixed-5 준비)

이어서 작업할 때 먼저 읽는 문서. 수치는 측정값, 판단은 "해석"으로 구분했다.

## 1. 오늘 한 일

| 순서 | 내용 | 결과 |
|---|---|---|
| 1 | 최종 데이터 fixed-4(v6 반영) 작성·시험 세트 통합(234문항)·백업·zip | 커밋 `978e617`, `0dd715d` push |
| 2 | 다른 노트북용 학습 인수인계 zip | `members/zips/q4b-v4-train-handoff.zip` (git 밖) |
| 3 | 병준 최신 소스(UI 11~17번) 반영, APK 재빌드, 서버 실행 | 커밋 `5121e70` push. 모델·데이터 파일은 제외 |
| 4 | 종목 DB 전체 수집 | 약 6분, 오류 0건. 일봉 +226행, 스냅샷 113개 갱신. 재무는 3분기 보고서가 11-14 제출 기한이라 거의 그대로 |
| 5 | haechan이 학습한 q4b-v4 어댑터 확인·이관·234문항 평가 | `outputs/q4b-v4/`, `outputs/eval_q4b-v4.jsonl` |
| 6 | 시험 정답 조사 오류 8건 수정(팀 합의) | 커밋 `43667ed` push |
| 7 | 문서 작성 | `q4b-v4-evaluation.md`, `fixed5-draft.md`, `fixed5-verification-checklist.md`, 본 문서 |
| 8 | 검증 스크립트 | `data/scripts/check_new_data.py` |

## 2. 현재 결과 (v4)

- 필드 정확도 95.3%, JSON 유효율 100%.
- 공식 111 완전 일치 75.7% → 정답 수정 후 79.3%(v3 65.8%). 전체 234문항 66.2%.
- 약점: 지표 모호 되묻기 2/9, 값 되묻기 14/18, haechan34 세트 35.3%.
- 상세는 `q4b-v4-evaluation.md`.

## 3. 결정된 것

- 8B·4B 모두 사용자가 만든 최종 데이터 fixed-4로 학습한다(팀 합의). 시험 파일은 `test_set.jsonl` 하나.
- 최종 데이터·시험 세트는 사용자가 담당이라 `git add -f`로 커밋·push 가능(예외). 다른 대용량 파일(어댑터·백업·zip)은 올리기 전 확인.
- 시험 정답 조사 오류 수정은 병준·haechan과 합의 완료.
- fixed-5 추가 데이터 생성은 **다른 팀원**이 한다. yappang은 검증한다(`fixed5-verification-checklist.md`).
- 학습은 사용자가 시작하라고 하기 전에는 하지 않는다.

## 4. 정정한 것 (오해 방지)

- 학습 데이터의 거절 문구 조사 오류는 **0건**이다(20개 밖 거절 317건). "약 30건"이라고 한 것은 정규식 오류였다.
- 종목 DB 수집은 끝나 있었다(12:43). "진행 중"이라고 한 것은 확인 명령이 자기 자신을 잡은 오판이었다.
- 지표 모호 건수 1,313(모든 응답 기준)과 1,237(마지막 응답 기준)은 집계 기준 차이다.

## 5. 아직 안 한 것 / 미결

| 항목 | 상태 |
|---|---|
| 새 문서·스크립트 커밋 | 미커밋: `docs/q4b-v4-evaluation.md`, `fixed5-draft.md`, `fixed5-verification-checklist.md`, 본 문서, `data/scripts/check_new_data.py` |
| `train_qlora.py` 경고 문구 수정 | 미커밋 |
| fixed-5 기준 확정 | "싸다" 후보 통일(10·11·16 vs 10·11), "매출이익률"(5·6·7)·"주요 활동 수익성"(5·7·8·9) 점검, 모호 판단 기준·메시지 규칙 확인 |
| 주제어 단위 후보 집합 분포 | 미집계 (후보 집합별로만 집계함) |
| 학습 데이터 JSON이 아닌 응답 599개 | 지표 설명 텍스트로 확인(검증 스크립트가 허용). 전체 내용은 안 읽음 |
| 구조 일치 보조 지표 | 미추가. 추가하면 문구 차이와 모델 오류를 분리 가능 |
| v4 어댑터 병합·GGUF·Ollama 적용 | 미진행. 합격 기준을 어떻게 볼지 결정 필요 |
| 8B와 같은 세트 비교 | 미요청 (haechan에게) |
| v4 학습 에폭·손실값 | haechan에게 로그 요청 필요 |
| 병준 UI 11~17번 화면 확인 | 서버 응답만 확인. 폰·브라우저 화면은 직접 못 봄 |
| `.env` 정리 | `EXTERNAL_MODE=live` → `fixture` 되돌려 달라는 요청이 남아 있음 |
| 종목 3분기 재무 | 11-14 이후 `collect_data.py --only dart` 재실행 |

## 6. 현재 환경 상태 (재부팅하면 꺼짐)

- 백엔드 8000, 프론트 5173 실행 중(로그 `/tmp/claude-1000/`). APK는 `C:\Users\Public\app-debug.apk`, 서버 주소 `192.168.0.13:8000`(Wi-Fi IP가 바뀌면 재빌드).
- 어댑터: `train_model_q4b/outputs/q4b-v4/`(git 밖), 원본 `members/zips/q4b-v4-adapter-haechan`.

## 7. 다음 순서 (제안)

1. 새 문서·스크립트 커밋·push.
2. 사용자와 fixed-5 기준 확정(`fixed5-draft.md` 3절).
3. 팀원에게 생성 요청서 전달(`fixed5-verification-checklist.md` 0절).
4. 받은 데이터를 `check_new_data.py`와 표본 검수로 검증.
5. 합쳐서 fixed-5 확정 → 학습은 사용자 지시 후 → v5 평가.

## 8. 참고 파일

- 평가: `outputs/eval_q4b-v4.jsonl`, `eval_q4b_v4.log`, `docs/q4b-v4-evaluation.md`
- 데이터: `train_model_q4b/data/`(`DATA_VERSION.md`, `TEST_SET.md`, `SHA256SUMS_data.txt`, `backup/2026-11-09/`)
- 생성 코드: `data/scripts/build_v4_data.py`, `build_test_set.py`, `check_new_data.py`
