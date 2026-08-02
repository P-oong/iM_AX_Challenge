# iM AX 챌린지 2026 — 지점 맞춤형 KPI 전담 에이전트 데모

"인사이동으로 떠나지 않는 지점 맞춤형 KPI 전담 에이전트" 아이디어의 필수 데이터·로직만
구현한 Streamlit 데모입니다. 설계 원칙은 **"판단은 AI가, 계산은 엔진이"** — 점수·구간·
ROI·벤치마킹은 전부 `src/scoring_engine.py` / `src/benchmarking.py`가 결정론적으로
계산하고, OpenAI GPT(`gpt-5.6-terra`)는 그 결과를 해석·브리핑·Q&A에만 사용합니다.

## 화면 구성

| 파일 | 화면 |
|---|---|
| `app.py` | 홈 (개요 · 총점 요약) |
| `pages/1_주간_전략_브리핑.py` | 3대 과제 카드 + 규정 요약 + 수용/보류 피드백 |
| `pages/2_지표_현황_히트맵.py` | 상한도달/진행/가성비/사각지대 시각화 |
| `pages/3_시뮬레이터.py` | "OO지표 N건 추가" → 총점 변화 즉시 계산 |
| `pages/4_규정_QA_챗.py` | 규정 Q&A (근거 없으면 "규정 확인 필요") |
| `pages/5_피드백_로그.py` | 누적 피드백 → 학습된 지점 규칙 |

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

OpenAI API 키 없이도 전 화면이 폴백(결정론적 템플릿)으로 정상 동작합니다.
실제 LLM 브리핑/Q&A를 사용하려면 프로젝트 루트의 `.env.example`을 복사해
`.env`로 저장하고 `OPENAI_API_KEY`를 채워주세요.

```bash
cp .env.example .env   # 그 다음 .env 파일에 실제 키 입력
```

`.env`는 `.gitignore`에 등록되어 있어 커밋되지 않으며, 키 조회 로직은
`src/config.py` 한 곳에서 관리됩니다 (이미 설정된 환경변수가 `.env`보다 우선).

## Streamlit Community Cloud 배포 (고정 URL)

1. 이 저장소를 GitHub에 push 합니다.
2. https://share.streamlit.io → "New app" → 저장소/브랜치/`app.py` 선택 후 배포.
   → 배포 즉시 `https://<임의문자열>.streamlit.app` 형태의 **고정 URL**이 생성됩니다.
   (앱 설정에서 커스텀 subdomain을 직접 지정할 수도 있습니다.)
3. OpenAI API를 쓰려면 앱 대시보드 → **Settings → Secrets**에 아래를 붙여넣습니다.
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
   Streamlit Cloud는 Secrets에 등록한 값을 환경변수로도 주입하므로, `.env` 파일 없이
   로컬과 동일한 코드(`src/config.py` → `os.environ`)로 그대로 동작합니다.
   (`.env`는 로컬 개발용이며 배포 저장소에는 올라가지 않습니다.)
4. 이후 GitHub에 커밋을 push할 때마다 **같은 URL**로 자동 재배포됩니다.
   → 지금 뼈대를 배포해 URL을 먼저 제출하고, 심사 전까지 계속 커밋을 쌓아
   완성도를 높이는 전략이 그대로 가능합니다.
5. 무료 티어 앱은 장시간 미접속 시 잠들 수 있습니다. 심사 직전에 URL에 한 번
   접속해 깨워두는 것을 권장합니다.

## 아직 사람이 해야 하는 일 (AI API 관련)

- `OPENAI_API_KEY` 발급(platform.openai.com) 및 Streamlit Cloud Secrets 등록 (위 3번).
- `src/llm_agent.py`의 프롬프트/스키마는 초안이므로, 실제 브리핑 문구 톤·형식을
  다듬으려면 프롬프트를 조정해 보며 결과를 확인하는 과정이 필요합니다.
- 비용/속도 튜닝이 필요하면 `src/llm_agent.py`의 `MODEL` 상수를 조정하세요. 현재는
  GPT-5.6 계열의 균형형 등급(`gpt-5.6-terra`)을 사용 중이며, 더 저렴한 등급이
  필요하면 비용 최적화형(`gpt-5.6-luna`)으로, 더 높은 품질이 필요하면 최상위
  프론티어 등급(`gpt-5.6-sol`)으로 바꿀 수 있습니다. (모델 라인업은 시점에 따라
  바뀌므로 배포 전 OpenAI 공식 문서에서 현재 모델명을 한 번 확인하는 것을 권장합니다.)

## 데이터에 대해

모든 실적·지점·피어그룹 데이터는 `src/data_generator.py`가 시드 기반으로 생성하는
가상 데이터입니다(실제 고객/거래 정보 없음). 사이드바에서 시드를 바꾸면 다른 가상
시나리오를 재현할 수 있고, 피드백 로그는 시드를 바꿔도 유지되어 "인사이동과 무관하게
축적되는 지점 메모리" 컨셉을 보여줍니다.
