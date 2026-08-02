"""
① 주간 전략 브리핑 — 3대 과제 카드 + 규정 요약 박스 + 수용/보류 피드백 버튼

[Phase 3 구조] 브리핑은 LangGraph 멀티에이전트 그래프가 생성한다:
  dispatch → 부문 에이전트 4개 병렬(fan-out) → Validator 검증
           → (문제 시 해당 부문만 재실행) → Supervisor 종합 → 최종 검증 → 완료

지점장이 [수용/보류] 버튼을 누르면 그 결정이 피드백 로그에 쌓이고,
⑤ 피드백 로그 화면에서 학습된 규칙으로 진화한다.
"""
import streamlit as st

from src import dept_facts, feedback_store, graph, scoring_engine, validator
from src.kpi_master import DEPARTMENTS
from src.state import append_feedback, get_data, sidebar_controls

st.set_page_config(page_title="주간 전략 브리핑", page_icon="📋", layout="wide")
sidebar_controls()

data = get_data()
computed = scoring_engine.compute_all(data["indicators"])
learned_rules = feedback_store.derive_rules(data["feedback_log"])
adjusted = feedback_store.apply_rules(computed, learned_rules)

# 연산엔진 결과를 부문별로 분배 (LLM 호출 없음 — 순수 Python)
all_dept_facts = dept_facts.build_all_dept_facts(
    DEPARTMENTS, adjusted, computed, learned_rules, data["branch_profile"]
)
# Validator가 대조할 '정답표' — 엔진이 계산한 원본 값
engine_index = validator.build_engine_index(computed)

st.title("📋 이번 주 전략 브리핑")
st.caption(f"기준일 {data['as_of']} · 잔여 {data['remaining_days']}영업일 · {data['branch_profile']['type']}")

if st.button("🔄 브리핑 다시 생성", help="에이전트 그래프를 다시 실행해 브리핑을 새로 생성합니다."):
    st.session_state.pop("briefing", None)

# 피드백이 쌓여 규칙이 바뀌면 브리핑도 다시 생성되어야 하므로 규칙 수를 캐시 키에 포함한다.
cache_key = (data["seed"], data["as_of"], len(learned_rules))
if "briefing" not in st.session_state or st.session_state.get("briefing_key") != cache_key:
    with st.status("에이전트 그래프 실행 중...", expanded=True) as status:
        status.write("🔀 4개 부문 전문 에이전트를 병렬 실행하고, Validator가 결과를 검증합니다...")
        st.session_state.briefing = graph.run_briefing_graph(
            all_dept_facts, learned_rules, data["branch_profile"], engine_index,
        )
        st.session_state.briefing_key = cache_key
        status.update(label="브리핑 생성 완료", state="complete", expanded=False)

briefing = st.session_state.briefing

st.subheader(briefing.get("headline", ""))

label_icon = {"구간 연산": "📐", "벤치마킹": "📊", "사각지대": "🔎"}
computed_by_name = {c["name"]: c for c in computed}

cols = st.columns(max(len(briefing.get("cards", [])), 1))
for i, card in enumerate(briefing.get("cards", [])):
    with cols[i % len(cols)]:
        with st.container(border=True):
            icon = label_icon.get(card["label"], "📌")
            st.caption(f"{icon} {card['label']}")
            st.markdown(f"**{card['indicator_name']}**")
            st.write(card["message"])

            ind = computed_by_name.get(card["indicator_name"])
            dept = ind["dept"] if ind else "공통"
            ind_id = ind["id"] if ind else ""

            reason = st.selectbox(
                "보류 시 사유", ["상권부적합", "인력부족", "고객군불일치", "기타"],
                key=f"reason_{i}", label_visibility="collapsed",
            )
            b1, b2 = st.columns(2)
            if b1.button("✅ 수용", key=f"accept_{i}", width="stretch"):
                append_feedback({
                    "date": data["as_of"], "dept": dept, "indicator_id": ind_id,
                    "indicator_name": card["indicator_name"], "decision": "수용", "reason": "-",
                })
                st.success("수용으로 기록되었습니다.")
            if b2.button("⏸ 보류", key=f"reject_{i}", width="stretch"):
                append_feedback({
                    "date": data["as_of"], "dept": dept, "indicator_id": ind_id,
                    "indicator_name": card["indicator_name"], "decision": "보류", "reason": reason,
                })
                st.warning(f"'{reason}' 사유로 보류 기록 — 3회 누적 시 지점 규칙으로 학습됩니다.")

st.divider()
st.markdown("#### 📎 배포용 규정 요약 (창구 교육 자료)")
with st.container(border=True):
    st.write(briefing.get("regulation_summary", ""))

if learned_rules:
    st.info("**학습된 지점 규칙이 이번 브리핑에 반영되었습니다:** " +
            " / ".join(r["rule_text"] for r in learned_rules))

st.divider()
st.markdown("#### 🛡️ Validator 검증 로그 (자기교정 루프)")
st.caption("에이전트 출력이 SOP 규칙을 지켰는지 검사한 기록입니다. 검증은 LLM이 아닌 "
           "결정론적 Python이 수행하며, 엔진이 계산한 원본 값과 직접 대조합니다. "
           "문제가 발견되면 해당 부문만 자동으로 다시 실행됩니다.")

validation_log = briefing.get("validation_log", [])
with st.container(border=True):
    if not validation_log:
        st.write("검증 기록이 없습니다.")
    for line in validation_log:
        if line.startswith("["):
            if "통과" in line:
                st.markdown(f"✅ {line}")
            elif "발견" in line:
                st.markdown(f"⚠️ {line}")
            else:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ {line}", unsafe_allow_html=True)
        else:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ {line}", unsafe_allow_html=True)

st.divider()
st.markdown("#### 🧩 부문별 에이전트 분석 결과")
st.caption("Supervisor가 최종 3대 과제를 확정하기 전에, 각 부문 에이전트가 올린 원본 안건입니다. "
           "부문별로 역할을 나눠 자기 분야 규칙만 집중 판단하도록 설계했습니다.")

dept_results = briefing.get("dept_results", {})
dept_tabs = st.tabs([f"{d} ({len(all_dept_facts.get(d, {}).get('indicators', []))}개 지표)" for d in DEPARTMENTS])
for tab, dept in zip(dept_tabs, DEPARTMENTS):
    with tab:
        result = dept_results.get(dept)
        if not result:
            st.write("분석 결과가 없습니다.")
            continue

        st.markdown(f"**{result.get('dept_summary', '')}**")

        recommendations = result.get("recommendations", [])
        if recommendations:
            for rec in recommendations:
                with st.container(border=True):
                    st.markdown(f"**{rec['indicator_name']}**")
                    st.write(rec["reason"])
                    st.caption(f"🗣️ 창구 안내: {rec['counter_guide']}")
                    st.caption(f"⚠️ 유의사항: {rec['caution']}")
        else:
            st.write("이 부문에서는 추천할 과제가 없습니다.")

        stops = result.get("stop_recommendations", [])
        if stops:
            st.warning("🛑 영업중단 권고 (상한 도달): " + ", ".join(stops))
