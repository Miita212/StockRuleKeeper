# haechan finetune 폴더: 다른 팀원·Claude가 읽기 전에 볼 것

**v1·v2(2026-11-05~06)의 학습 결과·어댑터·진단은 잘못된 학습 설정으로 나온 실패 기록이다. 참고하거나 따라 하지 말 것.**

- 원인: 예전 `train_qlora.py`의 `group_by_length=True`. 답 유형(거절·되묻기·추출)마다 길이가 달라서 배치가 한 유형으로 몰리고, 모델이 한 유형으로만 답하게 됐다(추출 정확도 0%).
- **이 설정(`group_by_length=True`)을 다른 학습 코드에 넣지 말 것.**
- 학습 코드를 참고하려면 현재 `train_qlora.py`(2026-11-06 수정본, group_by_length 기본 끔)나 `members/byungjun/finetune_train/train.py`를 볼 것. **2026-11-06 이전 커밋의 `train_qlora.py`는 쓰지 말 것.**
- 참고 금지 폴더: `results/eval_v1/`, `results/eval_v2/`, `results/diag/`, `results/adapter_v1-haechan/`, `results/adapter_v2_1ep-haechan/`, `results/train_logs/v1_train.log`, `results/train_logs/v2_1ep_train.log`, `prep_data_v2.py`·`run_v2_test.sh`(v2용, 데이터 비율 가설은 틀렸음)
- 참고해도 되는 결과: v3 이후(`*v3*-haechan`). 자세한 내용은 `results/RESULTS.md` 6절.
