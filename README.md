<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,24&height=220&section=header&text=StockRuleKeeper&fontSize=56&fontColor=ffffff&animation=fadeIn&fontAlignY=36&desc=%EC%A3%BC%EC%8B%9D%ED%88%AC%EC%9E%90%20%EC%9B%90%EC%B9%99%20%EC%A7%80%ED%82%B4%EC%9D%B4&descSize=22&descAlignY=58" alt="StockRuleKeeper 배너" />

<img src="https://readme-typing-svg.demolab.com?font=Noto+Sans+KR&weight=600&size=22&duration=3000&pause=1200&color=2563EB&center=true&vCenter=true&width=640&height=48&lines=%EB%A7%90%20%ED%95%9C%EB%A7%88%EB%94%94%EB%A1%9C%20%ED%88%AC%EC%9E%90%20%EC%9B%90%EC%B9%99%EC%9D%84%20%EC%84%B8%EC%9B%8C%EC%9A%94;20%EA%B0%9C%20%EC%A7%80%ED%91%9C%EB%A1%9C%20%EC%A2%85%EB%AA%A9%EC%9D%84%20%ED%8C%90%EC%A0%95%ED%95%B4%EC%9A%94;%EC%9B%90%EC%B9%99%EC%9D%84%20%EB%B0%94%EA%BE%B8%EB%A9%B4%20%EA%B2%B0%EA%B3%BC%EA%B0%80%20%EC%96%B4%EB%96%BB%EA%B2%8C%20%EB%8B%AC%EB%9D%BC%EC%A7%88%EA%B9%8C%3F" alt="말 한마디로 투자 원칙을 세워요 / 20개 지표로 종목을 판정해요 / 원칙을 바꾸면 결과가 어떻게 달라질까?" />

<br />

**"영업이익 500억원 이상인 회사만 보고 싶어요."**
<br />
이 한 문장이면 충분해요. 나머지는 StockRuleKeeper가 숫자로 바꾸고, 종목마다 지켰는지 알려 줘요.

<br />

![React](https://img.shields.io/badge/React-18-2563EB?style=for-the-badge&logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Qwen3-8B](https://img.shields.io/badge/Qwen3--8B-QLoRA-7C3AED?style=for-the-badge)
![Claude Haiku 5.5](https://img.shields.io/badge/Claude-Haiku%205.5-D97757?style=for-the-badge)

</div>

---

## 0. 프로그램의 목적과 결과

### 🎯 목적

- 투자 원칙을 세워도, 종목마다 그 원칙을 지켰는지 하나하나 확인하기는 어려워요.
- StockRuleKeeper는 **지표 이름을 몰라도 말로 원칙을 세우고**, 종목이 그 원칙을 **얼마나 지켰는지 숫자로 확인**하게 도와줘요.
- 원칙의 기준을 바꾸면 결과가 어떻게 달라지는지도 **과거 데이터 시뮬레이션으로 미리 비교**해 볼 수 있어요.
- 종목을 추천하거나 주가를 예측하는 앱이 아니라, **내 원칙을 지키도록 돕는 도구**예요.

### 🏁 결과

사용자가 앱에서 얻는 결과는 다음과 같아요.

| 사용자가 하는 일 | 앱이 돌려주는 결과 |
| --- | --- |
| 💬 원칙을 말로 이야기해요<br/>_"영업이익 500억원 이상인 회사만 보고 싶어요"_ | 20개 지표 중 **해당 지표를 골라 수치로 바꿔 줘요.**<br/>기준이 애매하면 **되묻고**, 예측·종목 추천은 **거절**해요. |
| 🧾 종목을 검색해요 | 내 원칙을 **몇 개 충족하는지** 알려 주는 판정서<br/>(예: 동진쎄미켐 **16 / 20개 충족**, 지표별 실제 값과 충족 여부) |
| 🗂️ 원칙을 관리해요 | 이름을 붙여 저장하고, 수치를 고치고, 지표를 잠그거나 꺼 둘 수 있어요. |
| 📈 원칙의 수치를 바꿔 봐요 | 바꾸기 **전·후 비교**(조건에 맞는 종목 수, 평균 수익률, 오른 종목 비율)와 **쉬운 말 리포트**<br/>(예: 부채비율 30% → 24%, 6개월 기준) |

그리고 말을 원칙으로 바꾸는 모델(Qwen3-8B QLoRA)은 264문항 평가에서 **전체 91.7%**를 기록했어요. (서버 4비트 환경, 팀 내부 평가)

> 표의 숫자는 실제 앱 화면에서 가져온 예시예요.

---

## 1. 프로그램의 흐름

<div align="center">
<img src="https://raw.githubusercontent.com/ByJn1224/stockrulekeeper-assets/main/demo.gif" width="260" alt="앱 사용 화면 슬라이드" />
<br />
<sub>원칙 만들기 → 되묻기 → 거절 → 판정서 → 수치 수정 → 리포트</sub>
</div>

### 1-1. 전체 사용 흐름

```mermaid
flowchart LR
    A["💬 원칙 만들기<br/>말로 이야기해요"] --> B["💾 이름 정해 저장"]
    B --> C["🧾 종목 검색<br/>판정서 확인"]
    B --> D["🗂️ 원칙 관리<br/>수정 · 잠금 · 끄기"]
    D --> C
    B --> E["📈 시뮬레이션<br/>기준 바꿔 비교"]
    E --> F["✍️ 리포트"]

    style A fill:#EFF6FF,stroke:#2563EB,color:#1E3A8A
    style C fill:#ECFDF5,stroke:#059669,color:#064E3B
    style E fill:#F5F3FF,stroke:#7C3AED,color:#4C1D95
    style F fill:#FFF7ED,stroke:#D97757,color:#7C2D12
```

앱 하단 메뉴는 **원칙 생성 · 원칙 관리 · 종목 검색 · 시뮬레이션 · 설정** 다섯 칸이고, 위 흐름의 각 단계와 하나씩 이어져 있어요.

### 1-2. 단계별 화면

#### ① 원칙 만들기

<table>
<tr>
<td align="center" width="33%"><img src="https://raw.githubusercontent.com/ByJn1224/stockrulekeeper-assets/main/1_extract.png" width="220" alt="추출" /><br /><b>추출</b><br />말한 내용을 지표 수치로 바꿔요</td>
<td align="center" width="33%"><img src="https://raw.githubusercontent.com/ByJn1224/stockrulekeeper-assets/main/2_clarify.png" width="220" alt="되묻기" /><br /><b>되묻기</b><br />기준이 애매하면 다시 물어봐요</td>
<td align="center" width="33%"><img src="https://raw.githubusercontent.com/ByJn1224/stockrulekeeper-assets/main/3_reject.png" width="220" alt="거절" /><br /><b>거절</b><br />예측·종목 추천은 정중히 거절해요</td>
</tr>
</table>

- 예: *"영업이익 500억원 이상인 회사만 보고 싶어요"* → 영업이익 **500억원 이상** 지표가 만들어져요.
- 만들어진 지표는 잠그거나, 수치를 직접 고치거나, 한 번 더 말해서 바꿀 수 있어요.
- 마음에 들면 **"이 원칙으로 시작해요"** 를 눌러 이름을 정해 저장해요.

#### ② 종목 판정서

<table>
<tr>
<td align="center" width="40%"><img src="https://raw.githubusercontent.com/ByJn1224/stockrulekeeper-assets/main/4_verdict.png" width="220" alt="종목 판정서" /></td>
<td>

종목 이름이나 코드로 검색하면, 내 원칙을 **몇 개 충족하는지**와 지표별 실제 값을 한 장으로 보여 줘요.

- 예: 동진쎄미켐 **16 / 20개 충족**
- 재무 건전성, 수익성 같은 묶음별로 **충족 / 미충족**을 확인해요.

</td>
</tr>
</table>

#### ③ 시뮬레이션과 리포트

<table>
<tr>
<td align="center" width="50%"><img src="https://raw.githubusercontent.com/ByJn1224/stockrulekeeper-assets/main/5_sim_edit.png" width="220" alt="수치 수정" /><br /><b>수치 수정</b><br />원칙의 수치를 바꿔 봐요</td>
<td align="center" width="50%"><img src="https://raw.githubusercontent.com/ByJn1224/stockrulekeeper-assets/main/6_report.png" width="220" alt="리포트" /><br /><b>리포트</b><br />바꾸기 전·후를 비교해 줘요</td>
</tr>
</table>

**원칙 선택 → 수치 수정 → 기간 선택 → 계산 → 리포트** 순서로 진행해요. 예를 들어 부채비율 기준을 30%에서 24%로 낮추면, 조건에 맞는 종목 수가 36개에서 23개로 줄어드는 식으로 결과를 비교해요. (배당은 포함하지 않아요.)

### 1-3. 내부 처리 흐름

```mermaid
flowchart LR
    A["💬 사용자의 말<br/>영업이익 500억원 이상인 회사만"] --> B["🤖 Qwen3-8B (QLoRA)<br/>말 → 지표·수치 변환"]
    B -->|추출| C["📋 20개 지표 원칙"]
    B -->|애매함| D["❓ 되묻기"]
    B -->|예측·추천| E["🚫 거절"]
    C --> F["🧾 종목 판정서"]
    C --> G["📈 시뮬레이션"]
    H[("🗄️ 재무·시세 데이터<br/>KIS · DART")] --> F
    H --> G
    G --> I["✍️ Claude Haiku 5.5<br/>쉬운 말 리포트"]

    style A fill:#EFF6FF,stroke:#2563EB,color:#1E3A8A
    style B fill:#F5F3FF,stroke:#7C3AED,color:#4C1D95
    style C fill:#ECFDF5,stroke:#059669,color:#064E3B
    style D fill:#FFFBEB,stroke:#D97706,color:#78350F
    style E fill:#FEF2F2,stroke:#DC2626,color:#7F1D1D
    style I fill:#FFF7ED,stroke:#D97757,color:#7C2D12
```

### 1-4. 단계별 사용 기술

| 단계 | 사용 기술 | 설명 |
| --- | --- | --- |
| 말 → 원칙 변환 | **Qwen3-8B + QLoRA 파인튜닝** | 직접 만든 학습 데이터로 *추출 · 되묻기 · 거절* 세 가지 동작을 익혔어요. |
| 시뮬레이션 리포트 | **Claude Haiku 5.5** | 비교 결과를 읽기 쉬운 글로 풀어 써 줘요. |
| 앱 화면 | React · Vite · TypeScript | 모바일 화면에 맞춘 UI예요. 토스 인앱 배포를 염두에 두고 만들었어요. |
| 서버 | FastAPI · SQLite | 원칙과 종목 지표를 저장하고 판정해요. |
| 데이터 | KIS · DART | 시세와 재무 데이터를 가져와 20개 지표를 계산해요. |

모델의 유형별 평가 점수예요. (264문항 = 검증 234 + 새 문항 30, 서버 4비트 환경의 팀 내부 평가)

| 추출 | 되묻기 | 거절 | 전체 |
| :---: | :---: | :---: | :---: |
| **96.1%** | **80.6%** | **93.3%** | **91.7%** |

---

## 2. 폴더 구성

### 2-1. 전체 구조

```text
StockRuleKeeper/
├─ README.md                  이 문서
├─ docs/
│  └─ interface.md            팀 공통 약속: 함수 이름·데이터 형식
├─ .github/
│  └─ pull_request_template.md  PR 작성 양식
└─ members/                   팀원별 작업 폴더 (각자 자기 폴더에서만 작업)
   ├─ byungjun/
   ├─ yappang/
   ├─ hyeonkyeong/
   └─ haechan/
```

- 각자 `members/자기이름/` 안에서만 작업해요. 다른 사람의 폴더와 공용 파일은 고치지 않아요.
- 함수 이름과 데이터 형식은 [docs/interface.md](docs/interface.md)에 맞춰요.
- 커밋 메시지는 `[이름] 한 일` 형식으로 써요. (예: `[byungjun] 파서 함수 추가`)

### 2-2. 앱 폴더 안쪽 (`backend/`, `frontend/`)

실제로 돌아가는 앱이에요. `byungjun`, `yappang`, `hyeonkyeong` 폴더에 같은 구조로 들어 있어요.

```text
backend/                        서버 (FastAPI + SQLite)
├─ main.py                      서버 시작 지점
├─ api/                         앱이 부르는 요청 주소 (원칙 · 종목 · 시뮬레이션)
├─ services/                    요청을 실제로 처리하는 로직
├─ indicators/                  20개 지표의 정의 · 계산 · 충족 판정
├─ llm/                         모델 연결 (말 → 원칙 변환, 리포트 작성)
├─ external/                    KIS · DART 연동 + 테스트용 샘플 응답(fixtures)
├─ db/                          SQLite 연결과 테이블 정의(schema.sql)
├─ batch/                       종목 목록 만들기 · 데이터 수집
├─ data/                        반도체 종목 목록 등 서버가 읽는 데이터
├─ scripts/                     연결 점검 · 동작 확인용 스크립트
├─ requirements.txt             필요한 파이썬 패키지
└─ .env.example                 환경변수 양식 (실제 .env는 올리지 않아요)

frontend/                       앱 화면 (React + Vite + TypeScript)
├─ src/
│  ├─ screens/                  화면들 (원칙 채팅, 종목 검색, 판정서, 시뮬레이션 …)
│  ├─ components/               버튼 · 말풍선 · 지표 카드 같은 공통 부품
│  ├─ layouts/                  하단 메뉴가 있는 공통 틀
│  ├─ store/                    앱 전체에서 같이 쓰는 상태
│  └─ api/                      서버 호출 함수
├─ android/                     안드로이드 앱 빌드용 (Capacitor)
├─ apps-in-toss.config.ts       토스 인앱 배포 설정
└─ package.json                 실행 · 빌드 명령과 필요한 패키지

virtual-app/                    앱 밖에서 앱 열기를 시험하는 가상 주식앱 페이지
```

### 2-3. 모델·데이터 폴더

말을 원칙으로 바꾸는 모델(Qwen3-8B)을 만들고 평가한 자료예요. 팀원 폴더 안에 있어요.

| 폴더 | 의미 | 위치 |
| --- | --- | --- |
| `data/` | 학습 데이터를 만드는 스크립트와 지표 정리, 검증 자료 | 모든 팀원 폴더 |
| `finetune_merged/` | 팀원 데이터를 합친 최종 학습·검증 데이터 | `byungjun` |
| `finetune_train/` | 학습 · 병합 · 평가 코드, 학습한 모델을 앱에 연결하는 스크립트 | `byungjun` |
| `data_fixed5_hk/`, `data_fixed6_hk/` | 오류를 고쳐 다시 만든 학습·평가 데이터 (fixed-6가 최종 모델의 데이터) | `hyeonkyeong` |
| `finetune_v1.0/` | Qwen3-8B 학습 · 평가 · 내보내기 코드와 실행 가이드 | `hyeonkyeong` |
| `finetune/`, `training-results-haechan/` | 학습 코드, 버전별 데이터, 학습 결과와 평가 기록 | `haechan` |
| `q4b-finetune-haechan/`, `train_model_q4b/` | 작은 모델(Qwen3 4B)로 한 학습 자료 | `haechan`, `yappang` |
| `docs/` | 작업 기록, 평가 결과, 모델 선정 과정 같은 문서 | `byungjun`, `yappang`, `hyeonkyeong` |

---

## 3. 실행 방법 (step by step)

(아래는 `members/byungjun/` 폴더 기준이에요. `yappang`, `hyeonkyeong` 폴더도 같은 구조라서 폴더 이름만 바꾸면 똑같이 돼요.)

### 준비물

| 준비물 | 확인한 버전 | 비고 |
| --- | --- | --- |
| Python | 3.12 | 서버 실행 |
| Node.js · npm | 24 | 앱 화면 실행 |
| Git | - | 저장소 받기 |
| API 키 | - | **실제 모드에서만** 필요해요 (KIS · DART · Anthropic) |
| Ollama · 모델 파일(약 5GB) | - | **실제 모드에서만** 필요해요 (Step 6) |

### 어떤 모드로 돌릴까요?

| | 🧪 체험 모드 (처음엔 이걸로!) | 🚀 실제 모드 |
| --- | --- | --- |
| 필요한 것 | 없음 (키 · 모델 불필요) | KIS · DART · Anthropic 키, Ollama와 모델 파일 |
| 데이터 | 비어 있어요. 종목 이름만 있고 시세·재무는 "데이터 없음"으로 나와요 | 한투 · DART에서 받아 DB에 저장 (Step 5, 필수) |
| 말 → 원칙 변환 | 말과 상관없이 **고정된 샘플 결과** | 모델이 실제로 변환 |
| 용도 | 화면 구성과 원칙 만들기 흐름 둘러보기 (판정서 · 시뮬레이션 값은 비어 있음) | 시연 · 실제 사용 |

### Step 1. 저장소 받기

```bash
git clone https://github.com/Miita212/StockRuleKeeper.git
cd StockRuleKeeper/members/byungjun
```

### Step 2. 서버 패키지 설치

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows(PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 3. 환경변수 파일 만들기

```bash
cp .env.example .env               # Windows: copy .env.example .env
```

`.env`를 열어 모드에 맞게 바꿔요. **`.env`는 키가 들어가므로 절대 올리지 않아요.**

```ini
# 🧪 체험 모드: 이 한 줄만 바꾸면 돼요
EXTERNAL_MODE=fixture

# 🚀 실제 모드: 아래 값을 채워요
EXTERNAL_MODE=live
KIS_APP_KEY=...
KIS_APP_SECRET=...
DART_API_KEY=...
ANTHROPIC_API_KEY=...             # 시뮬레이션 리포트는 항상 Claude Haiku 5.5예요
LLM_PROVIDER=local                # 말 → 원칙 변환을 파인튜닝 모델로 (Step 6 참고)
LOCAL_LLM_MODEL=qwen3-8b-fixed6   # Ollama에 등록한 모델 이름
```

### Step 4. 서버 실행하고 확인하기

`backend/` 폴더에서 실행해요.

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

- 처음 실행하면 DB(`backend/data/stockrule.db`)가 **자동으로 만들어지고** 종목 목록이 채워져요.
- 브라우저에서 확인해요.
  - http://localhost:8000/health → `{"ok":true, ...}` 가 보이면 성공
  - http://localhost:8000/docs → 서버가 제공하는 요청 목록(API 문서)

### Step 5. 데이터 받아 두기 (🚀 실제 모드는 필수)

DB 파일(`stockrule.db`)은 저장소에 없어서, 처음 받으면 종목 이름만 있고 시세·재무 데이터는 비어 있어요. 특히 재무 지표는 DB에 저장된 값만 쓰기 때문에 이 단계를 꼭 해야 판정서와 시뮬레이션에 값이 나와요. `backend/` 폴더에서 실행해요.

```bash
python batch/collect_data.py                    # 전체 (한투 약 10분 + DART 약 10분)
python batch/collect_data.py --codes 005930 000660   # 일부 종목만
```

이미 받은 종목은 건너뛰고 이어서 받아요. (다시 받으려면 `--force`) 팀원이 만들어 둔 `stockrule.db`를 받아 `backend/data/`에 넣어도 돼요.

> 🧪 체험 모드에서도 같은 명령(`--codes 005930`)으로 샘플 데이터를 채울 수 있지만, 일부 지표만 채워져요.

### Step 6. 말 → 원칙 모델 연결하기 (🚀 실제 모드만)

파인튜닝한 모델(Qwen3-8B + fixed-6 어댑터를 합쳐 4비트로 줄인 파일, 약 5GB)은 Hugging Face에 올려 두었어요. 받아서 Ollama에 등록하면 끝나요.

1. [Ollama](https://ollama.com)를 설치하고 켜요. (기본 주소 `http://localhost:11434`)
2. 모델 파일을 받아요. ([모델 저장소](https://huggingface.co/availablename2/stockrulekeeper-qwen3-8b-fixed6))

   ```bash
   pip install -U huggingface_hub
   hf download availablename2/stockrulekeeper-qwen3-8b-fixed6 --local-dir srk-model
   ```

3. Ollama에 등록해요.

   ```bash
   cd srk-model
   ollama create qwen3-8b-fixed6 -f Modelfile
   ollama list                       # qwen3-8b-fixed6 가 보이면 성공
   ```

4. `backend/.env`에 모델 이름을 적어요.

   ```ini
   LLM_PROVIDER=local
   LOCAL_LLM_MODEL=qwen3-8b-fixed6
   ```

> 모델 없이 실제 모드를 써 보고 싶다면 `.env`에서 `LLM_PROVIDER=anthropic`으로 바꿔요. 말 → 원칙 변환도 Claude가 해 줘요.

<details>
<summary>학습한 어댑터에서 직접 만들고 싶다면</summary>

위 파일은 아래 순서로 만든 결과예요. 베이스 모델 `Qwen/Qwen3-8B`(약 16GB)는 Hugging Face에서 받아요.

```bash
hf download Qwen/Qwen3-8B --local-dir models/Qwen3-8B
bash finetune_train/swap_adapter.sh <어댑터폴더> qwen3-8b-fixed6
```

`swap_adapter.sh`는 병준 PC 기준 경로(`/home/ai/llm_models` 등)와 llama.cpp 빌드가 필요해서, 내 환경에 맞게 고쳐서 써야 해요. 어댑터 파일은 저장소에 올리지 않아요.

</details>

### Step 7. 앱 화면 실행하기

새 터미널을 열어서 `frontend/` 폴더에서 실행해요. (서버는 켜 둔 채로)

```bash
cd frontend
npm install
npm run dev
```

터미널에 나온 주소(기본 http://localhost:5173)를 브라우저에서 열면 돼요. **모바일 화면 크기**(개발자 도구의 폰 보기)로 보면 가장 잘 보여요.

- 서버 주소를 바꾸려면 `frontend/.env`에 `VITE_API_BASE=http://서버주소:8000` 을 적어요. (기본값은 `http://localhost:8000`)
- 폰으로 보려면 노트북과 같은 Wi-Fi에서 노트북의 주소로 접속해요.

### Step 8. 가상 주식앱 열어 보기

서버가 켜져 있으면 http://localhost:8000/virtual-app/ 에서 가상 주식앱 페이지를 볼 수 있어요.

### 막힐 때

| 증상 | 확인할 것 |
| --- | --- |
| 앱에 "서버 연결 실패"가 떠요 | 서버(Step 4)가 켜져 있는지, `VITE_API_BASE` 주소가 맞는지 |
| `Address already in use` | 같은 포트를 쓰는 프로그램이 있어요. 끄거나 `--port 8001`처럼 다른 포트로 실행해요. |
| 말을 보냈는데 계속 같은 결과가 나와요 | 🧪 체험 모드(`EXTERNAL_MODE=fixture`)라서 그래요. 실제 모드로 바꿔요. |
| 실제 모드에서 모델이 응답하지 않아요 | Ollama가 켜져 있는지, `LOCAL_LLM_MODEL` 이름이 등록한 모델과 같은지 |

---

## 4. 팀원과 한 일

| 훈련생 | 깃허브 아이디 | 작업 폴더 | 담당 업무 |
| --- | --- | --- | --- |
| **정해찬** | [`Miita212`](https://github.com/Miita212) | `members/haechan/` | • 4080 QLoRA 파인튜닝 · 평가 (v1~v7)<br/>• 학습 데이터 보강<br/>• 4B 비교 학습<br/>• 문서 작성 |
| **한병준** | [`ByJn1224`](https://github.com/ByJn1224) | `members/byungjun/` | • 데이터 호출 구조<br/>• 학습 데이터 병합본과 학습 설정 명세<br/>• UX/UI 및 백엔드 구체화 |
| **이현경** | [`gonggong77`](https://github.com/gonggong77) | `members/hyeonkyeong/` | • 백엔드 LLM 연동<br/>• 앱 및 종목 DB 구현<br/>• 4090 서버 8B 재학습 (앱 모델)<br/>• 초기 UX/UI 설계 및 디자인 |
| **김병수** | [`yappang`](https://github.com/yappang) | `members/yappang/` | • 학습 데이터 생성<br/>• 평가셋 111건<br/>• 4B 시연 모델 트랙<br/>• 통합 데이터(fixed-4)와 Ollama 등록 절차<br/>• DB 설계 및 구현 |

---

## ⚠️ 알려 드려요

- StockRuleKeeper는 **투자 원칙을 지키도록 돕는 도구**예요. 종목을 추천하거나 주가를 예측하지 않아요.
- 시뮬레이션은 **지난 데이터로 계산한 결과**이고, 앞으로의 수익을 보장하지 않아요.
- 투자 판단과 결과에 대한 책임은 사용자 본인에게 있어요.

<div align="center">

<sub>동국대학교 DAIVE 1기 · 장예찬팀</sub>

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,24&height=100&section=footer" alt="" />

</div>
