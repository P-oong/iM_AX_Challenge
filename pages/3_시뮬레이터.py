"""
③ 시뮬레이터 — "OO지표 N건 추가" 입력 시 총점/등급 변화를 즉시 계산

계산은 전부 scoring_engine(결정론적 연산엔진)이 수행한다. 이 화면은 순수 UI이며
LLM 호출이 전혀 없다 — "계산 로직이 실제 규정과 일치하는가"를 검증하는 화면이므로
연산 과정에 어떤 모델도 개입시키지 않는 것이 설계 의도다.
"""
import streamlit as st

from src import kpi_master, scoring_engine
from src.state import get_data, sidebar_controls

st.set_page_config(page_title="시뮬레이터", page_icon="🧮", layout="wide")
sidebar_controls()

data = get_data()
computed = scoring_engine.compute_all(data["indicators"])
before_total = scoring_engine.total_score(computed)

st.title("🧮 KPI 시뮬레이터")
st.caption("특정 지표에 실적을 추가로 가정했을 때, 총점과 구간 통과 여부가 어떻게 바뀌는지 확인합니다.")

dept = st.selectbox("부문 선택", kpi_master.DEPARTMENTS)
dept_indicators = [c for c in computed if c["dept"] == dept]
ind_names = [c["name"] for c in dept_indicators]
selected_name = st.selectbox("지표 선택", ind_names)
selected = next(c for c in dept_indicators if c["name"] == selected_name)

st.markdown(
    f"**{selected['name']}** — 현재 실적 {selected['current_value']}{selected['unit']}, "
    f"현재 점수 {selected['current_score']}/{selected['max_score']}점"
)
if selected["next_hurdle"]:
    st.caption(
        f"다음 구간까지 {selected['gap']}{selected['unit']} 필요 → 통과 시 +{selected['score_gain']}점 "
        f"(구간 임계값: {selected['next_hurdle']['threshold']}{selected['unit']})"
    )
else:
    st.caption("이미 만점 구간에 도달했습니다.")

added = st.number_input(f"추가로 가정할 실적 ({selected['unit']})", min_value=0.0,
                         value=float(selected["gap"]) if selected["gap"] else 1.0, step=1.0)

if st.button("▶ 시뮬레이션 실행", type="primary"):
    after_computed = scoring_engine.simulate_addition(computed, selected["id"], added)
    after_total = scoring_engine.total_score(after_computed)
    after_selected = next(c for c in after_computed if c["id"] == selected["id"])

    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("당점 총점 (변경 전)", f"{before_total['current']} / {before_total['max']}점",
               f"{before_total['pct']}%")
    c2.metric("당점 총점 (변경 후)", f"{after_total['current']} / {after_total['max']}점",
               f"{after_total['pct']}%", delta=f"{after_total['current'] - before_total['current']:+d}점")

    st.markdown(f"#### '{selected['name']}' 지표 변화")
    d1, d2, d3 = st.columns(3)
    d1.metric("실적", f"{after_selected['current_value']}{selected['unit']}",
              f"+{added}{selected['unit']}")
    d2.metric("점수", f"{after_selected['current_score']}/{after_selected['max_score']}점",
              f"{after_selected['current_score'] - selected['current_score']:+d}점")
    d3.metric("상태", after_selected["category"])

    if after_selected["is_maxed"] and not selected["is_maxed"]:
        st.success("🎉 이 실적 추가로 해당 지표가 만점 구간에 도달합니다 — 이후 영업력은 다른 지표로 전환하세요.")
    elif after_selected["current_score"] > selected["current_score"]:
        st.info("구간을 통과하여 점수가 상승했습니다.")
    else:
        st.warning("아직 다음 구간에 도달하지 못했습니다. 추가 실적을 늘려보세요.")
