"""
iM AX 챌린지 2026 — "인사이동으로 떠나지 않는 지점 맞춤형 KPI 전담 에이전트" 데모

이 파일은 앱의 홈(개요) 화면이다. 실제 5개 기능 화면은 좌측 사이드바의
pages/ 목록(주간 전략 브리핑 / 지표 현황 히트맵 / 시뮬레이터 / 규정 Q&A 챗 / 피드백 로그)에서 확인한다.
"""
import streamlit as st

from src import scoring_engine, theme, ui_helpers
from src.state import get_data, sidebar_controls

st.set_page_config(page_title="iM AX 챌린지 - KPI 전담 에이전트", page_icon="🏦", layout="wide")

theme.apply_background()
sidebar_controls()
data = get_data()
computed = scoring_engine.compute_all(data["indicators"])
total = scoring_engine.total_score(computed)

# 전주 대비 총점 변화 — 지표별 '1주 전 실적'으로 재계산한 총점과 비교한다.
# 이번 달 영업일이 아직 1주 미만이면 value_last_week가 없어 현재값을 그대로 사용(=변화 0).
last_week_raw = [
    {**ind, "current_value": ind["value_last_week"] if ind.get("value_last_week") is not None else ind["current_value"]}
    for ind in data["indicators"]
]
last_week_total = scoring_engine.total_score(scoring_engine.compute_all(last_week_raw))
weekly_score_delta = total["current"] - last_week_total["current"]

theme.show_banner("hero")

st.title("🏦 지점 맞춤형 KPI 전담 에이전트")
st.caption("iM AX 챌린지 2026 · 인사이동으로 떠나지 않는 '영속적인 디지털 부지점장'")

st.markdown(
    """
**'판단은 AI가, 계산은 엔진이'** — 점수·구간·ROI·벤치마킹은 전부 결정론적 연산엔진이 계산하고,
LLM 에이전트는 그 결과를 해석·브리핑·Q&A에만 사용합니다. 에이전트가 인용한 모든 수치는
Validator가 엔진 원본과 대조 검증합니다.
"""
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("당점 현재 KPI 점수", f"{total['current']} / {total['max']}점 ({total['pct']}%)",
              f"{weekly_score_delta:+d}점 (전주 대비)")
with col2:
    st.metric("상권 유형", data["branch_profile"]["type"])
with col3:
    st.metric("잔여 영업일 (이번 달)", f"{data['remaining_days']}일")
with col4:
    profile = data["branch_profile"]
    st.metric("지점 규모", f"{profile['scale']} · 직원 {profile['staff_count']}명",
              help=f"지난 분기 KPI 등급: {profile['prior_quarter_grade']}")

st.divider()

# ── 핵심 기능: 주간 전략 브리핑 강조 ──────────────────────────────
st.subheader("⭐ 핵심 기능 — 주간 전략 브리핑")
h1, h2, h3 = st.columns(3)
with h1, st.container(border=True):
    st.markdown("**📐 이번 주 3대 과제 선별**")
    st.write("부문별 전문 에이전트 4명이 30개 지표를 병렬 분석해, 지금 1~2건만 더 하면 "
             "점수가 급등하는 '가성비 과제'를 족집게처럼 골라냅니다.")
    st.caption("각 과제마다 구간 배점표·평가기준·규정 원문까지 바로 확인")
with h2, st.container(border=True):
    st.markdown("**🛡️ 수치 검증 후 보고**")
    st.write("에이전트가 인용한 실적·필요건수·예상점수를 Validator가 연산엔진 원본과 "
             "전수 대조합니다. 불일치가 발견되면 해당 부문만 자동 재분석합니다.")
    st.caption("출처 없는 숫자는 브리핑에 실리지 않음")
with h3, st.container(border=True):
    st.markdown("**📨 전 직원 즉시 배포**")
    st.write("확정된 브리핑과 창구 안내 문구를 그대로 지점 메신저로 발송해, "
             "그 주의 현장 교육 자료로 씁니다. 별도 툴 접속이 필요 없습니다.")
    st.caption("주간 아침 자동 발송 (데모: 발송 시뮬레이션)")

if st.button("📋 주간 전략 브리핑 바로가기", type="primary"):
    st.switch_page("pages/1_주간_전략_브리핑.py")

st.divider()

# ── 에이전트 라인업 ──────────────────────────────────────────────
st.subheader("🤖 이 지점에서 일하는 에이전트들")
st.caption("수십 개 지표를 하나의 AI에 몰아넣으면 중간 내용을 누락하는 '지시 희석 현상'이 생깁니다. "
           "그래서 부문별로 전문 에이전트를 나누고, Supervisor가 종합하며, Validator가 검증합니다.")
ui_helpers.render_agent_lineup(compact=False)

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
| ① 주간 전략 브리핑 ⭐ | 3대 과제 + 상세 배점표 + 부문 에이전트 분석 + 전 직원 전송 |
| ② 지표 현황 히트맵 | 상한도달(회색) · 진행(녹색) · 가성비(적색) · 사각지대(주황) 시각화 |
| ③ 시뮬레이터 | "OO지표 N건 추가" 입력 시 총점 변화 즉시 계산 |
| ④ 규정 Q&A 챗 | 자연어 질문 → 근거 발췌 기반 답변 (근거 없으면 "규정 확인 필요") |
| ⑤ 피드백 로그 | 누적 보류 사유 → 학습된 지점 고유 규칙 확인 |
"""
)
