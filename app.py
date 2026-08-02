"""
iM AX 챌린지 2026 — "인사이동으로 떠나지 않는 지점 맞춤형 KPI 전담 에이전트" 데모

이 파일은 앱의 홈(개요) 화면이다. 실제 5개 기능 화면은 좌측 사이드바의
pages/ 목록(주간 전략 브리핑 / 지표 현황 히트맵 / 시뮬레이터 / 규정 Q&A 챗 / 피드백 로그)에서 확인한다.
"""
import streamlit as st

from src import scoring_engine
from src.state import get_data, sidebar_controls

st.set_page_config(page_title="iM AX 챌린지 - KPI 전담 에이전트", page_icon="🏦", layout="wide")

sidebar_controls()
data = get_data()
computed = scoring_engine.compute_all(data["indicators"])
total = scoring_engine.total_score(computed)

st.title("🏦 지점 맞춤형 KPI 전담 에이전트")
st.caption("iM AX 챌린지 2026 · 아이디어 제안 데모 (필수 데이터·로직 중심 MVP)")

st.markdown(
    """
'판단은 AI가, 계산은 엔진이' 원칙에 따라, 점수·구간·ROI·벤치마킹은 전부 결정론적
연산엔진이 계산하고, Claude는 그 결과를 해석·브리핑·Q&A에만 사용합니다.
좌측 사이드바에서 5개 데모 화면을 확인하세요.
"""
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("당점 현재 KPI 점수", f"{total['current']} / {total['max']}점", f"{total['pct']}%")
with col2:
    st.metric("상권 유형", data["branch_profile"]["type"])
with col3:
    st.metric("잔여 영업일 (이번 달)", f"{data['remaining_days']}일")

st.divider()

cat_labels = {"상한도달": "🔘 상한도달", "가성비": "🔴 가성비 지표", "사각지대": "🟠 사각지대", "진행": "🟢 진행중"}
counts = {c: 0 for c in cat_labels}
for c in computed:
    counts[c["category"]] += 1

st.subheader("지표 현황 요약")
cols = st.columns(4)
for col, (cat, label) in zip(cols, cat_labels.items()):
    col.metric(label, f"{counts[cat]}개")

st.divider()
st.subheader("📋 데모 화면 안내")
st.markdown(
    """
| 화면 | 핵심 내용 |
|---|---|
| ① 주간 전략 브리핑 | 3대 과제 카드 + 규정 요약 박스 + 수용/보류 피드백 버튼 |
| ② 지표 현황 히트맵 | 상한도달(회색) · 진행(녹색) · 가성비(적색) · 사각지대(주황) 시각화 |
| ③ 시뮬레이터 | "OO지표 N건 추가" 입력 시 총점 변화 즉시 계산 |
| ④ 규정 Q&A 챗 | 자연어 질문 → 근거 발췌 기반 답변 (근거 없으면 "규정 확인 필요") |
| ⑤ 피드백 로그 | 누적 보류 사유 → 학습된 지점 고유 규칙 확인 |
"""
)
