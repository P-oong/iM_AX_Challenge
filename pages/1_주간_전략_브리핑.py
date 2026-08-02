"""
① 주간 전략 브리핑 (핵심 화면) — 3대 과제 + 상세 KPI 데이터 + 부문 에이전트 분석 + 전 직원 전송

[Phase 3 구조] 브리핑은 LangGraph 멀티에이전트 그래프가 생성한다:
  dispatch → 부문 에이전트 4개 병렬(fan-out) → Validator 검증
           → (문제 시 해당 부문만 재실행) → Supervisor 종합 → 최종 검증 → 완료

화면 구성:
  1. 3대 과제 카드 — 각 카드에 '어느 부문 에이전트가 올린 안건인지' 배지 표시,
     펼치면 구간 배점표·평가기준·규정 원문까지 확인 가능
  2. 부문별 에이전트 분석 결과 — 어떤 안건이 최종 채택됐는지 표시
  3. 전 직원 전송 — 확정 브리핑을 그대로 지점 메신저로 발송(시뮬레이션)
"""
import streamlit as st

from src import dept_facts, feedback_store, graph, scoring_engine, theme, ui_helpers, validator
from src.kpi_master import DEPARTMENTS
from src.state import append_feedback, get_data, sidebar_controls

st.set_page_config(page_title="주간 전략 브리핑", page_icon="📋", layout="wide")

theme.apply_background()
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

theme.show_banner("briefing_banner")

st.title("📋 이번 주 전략 브리핑")
st.caption(f"기준일 {data['as_of']} · 잔여 {data['remaining_days']}영업일 · "
           f"{data['branch_profile']['type']} · 직원 {data['branch_profile']['staff_count']}명")

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
dept_results = briefing.get("dept_results", {})
computed_by_name = {c["name"]: c for c in computed}

# 지표명 → 그 지표를 올린 부문 에이전트 (카드에 출처 배지를 달기 위함)
proposer_of = {
    rec["indicator_name"]: dept
    for dept, result in dept_results.items()
    for rec in result.get("recommendations", [])
}
# 최종 채택된 지표 (부문별 탭에서 '채택됨' 표시용)
adopted_names = {c["indicator_name"] for c in briefing.get("cards", [])}

# ──────────────────────────────────────────────────────────────────
# 1) 3대 과제
# ──────────────────────────────────────────────────────────────────
st.subheader(briefing.get("headline", ""))
st.caption("💡 각 과제 카드 아래 **'상세 KPI 데이터·평가기준 보기'** 를 펼치면 "
           "구간별 배점표와 본부 지침서 원문까지 그 자리에서 확인할 수 있습니다.")

label_icon = {"구간 연산": "📐", "벤치마킹": "📊", "사각지대": "🔎"}

cols = st.columns(max(len(briefing.get("cards", [])), 1))
for i, card in enumerate(briefing.get("cards", [])):
    name = card["indicator_name"]
    ind = computed_by_name.get(name)
    dept = ind["dept"] if ind else proposer_of.get(name, "공통")
    agent = ui_helpers.AGENT_PROFILES.get(dept, {})

    with cols[i % len(cols)]:
        with st.container(border=True):
            top = st.columns([3, 2])
            top[0].caption(f"{label_icon.get(card['label'], '📌')} {card['label']}")
            # 출처 배지 — 어느 부문 에이전트가 올린 안건인지
            top[1].caption(f"{agent.get('icon', '🤖')} {dept} 에이전트 제안")

            st.markdown(f"### {name}")
            st.write(card["message"])

            if ind:
                m1, m2 = st.columns(2)
                m1.metric("현재 점수", f"{ind['current_score']} / {ind['max_score']}점")
                if ind["next_hurdle"]:
                    m2.metric("다음 구간까지", f"{ind['gap']}{ind['unit']}",
                              f"+{ind['score_gain']}점")
                else:
                    m2.metric("다음 구간까지", "만점")

                with st.expander("📊 상세 KPI 데이터 · 평가기준 보기"):
                    ui_helpers.render_indicator_detail(ind)

            st.divider()
            reason = st.selectbox(
                "보류 시 사유", ["상권부적합", "인력부족", "고객군불일치", "기타"],
                key=f"reason_{i}", label_visibility="collapsed",
            )
            b1, b2 = st.columns(2)
            if b1.button("✅ 수용", key=f"accept_{i}", width="stretch"):
                append_feedback({
                    "date": data["as_of"], "dept": dept,
                    "indicator_id": ind["id"] if ind else "",
                    "indicator_name": name, "decision": "수용", "reason": "-",
                })
                st.success("수용으로 기록되었습니다.")
            if b2.button("⏸ 보류", key=f"reject_{i}", width="stretch"):
                append_feedback({
                    "date": data["as_of"], "dept": dept,
                    "indicator_id": ind["id"] if ind else "",
                    "indicator_name": name, "decision": "보류", "reason": reason,
                })
                st.warning(f"'{reason}' 사유로 보류 기록 — 3회 누적 시 지점 규칙으로 학습됩니다.")

st.markdown("#### 📎 배포용 규정 요약 (창구 교육 자료)")
with st.container(border=True):
    st.write(briefing.get("regulation_summary", ""))

if learned_rules:
    st.info("**학습된 지점 규칙이 이번 브리핑에 반영되었습니다:** " +
            " / ".join(r["rule_text"] for r in learned_rules))

st.divider()

# ──────────────────────────────────────────────────────────────────
# 2) 전 직원 전송
# ──────────────────────────────────────────────────────────────────
ui_helpers.render_dispatch_section(briefing, data)

st.divider()

# ──────────────────────────────────────────────────────────────────
# 3) 이 브리핑을 만든 에이전트들
# ──────────────────────────────────────────────────────────────────
st.markdown("#### 🤖 이 브리핑을 만든 에이전트들")
st.caption("30개 지표를 하나의 AI에 몰아넣으면 중간 내용을 누락하는 '지시 희석 현상'이 생깁니다. "
           "부문별로 전문 에이전트를 나눠 자기 분야 규칙만 집중 판단하게 하고, "
           "Supervisor가 동일 척도로 비교해 최종 확정합니다.")
ui_helpers.render_agent_lineup(compact=True)

st.markdown("##### 부문별 안건 → 최종 브리핑 반영 결과")
st.caption("각 부문 에이전트가 올린 원본 안건입니다. Supervisor가 채택한 안건에는 ⭐ 표시가 붙습니다.")

adopted_count = sum(1 for d in dept_results.values()
                    for r in d.get("recommendations", [])
                    if r["indicator_name"] in adopted_names)
total_proposed = sum(len(d.get("recommendations", [])) for d in dept_results.values())
st.markdown(f"**총 {total_proposed}건 상정 → {adopted_count}건 채택**")

dept_tabs = st.tabs([
    f"{ui_helpers.AGENT_PROFILES[d]['icon']} {d} "
    f"({sum(1 for r in dept_results.get(d, {}).get('recommendations', []) if r['indicator_name'] in adopted_names)}/"
    f"{len(dept_results.get(d, {}).get('recommendations', []))} 채택)"
    for d in DEPARTMENTS
])
for tab, dept in zip(dept_tabs, DEPARTMENTS):
    with tab:
        profile = ui_helpers.AGENT_PROFILES[dept]
        st.caption(f"**{profile['title']}** — {profile['specialty']}")

        result = dept_results.get(dept)
        if not result:
            st.write("분석 결과가 없습니다.")
            continue

        st.markdown(f"**분석 요약:** {result.get('dept_summary', '')}")

        recommendations = result.get("recommendations", [])
        if recommendations:
            for rec in recommendations:
                name = rec["indicator_name"]
                is_adopted = name in adopted_names
                with st.container(border=True):
                    head = st.columns([4, 1])
                    head[0].markdown(f"**{name}**")
                    head[1].markdown("⭐ **채택**" if is_adopted else "· 미채택")
                    st.write(rec["reason"])
                    st.caption(f"🗣️ 창구 안내: {rec['counter_guide']}")
                    st.caption(f"⚠️ 유의사항: {rec['caution']}")

                    ind = computed_by_name.get(name)
                    if ind:
                        with st.expander("📊 상세 KPI 데이터 · 평가기준 보기"):
                            ui_helpers.render_indicator_detail(ind)
        else:
            st.write("이 부문에서는 추천할 과제가 없습니다.")

        stops = result.get("stop_recommendations", [])
        if stops:
            st.warning("🛑 영업중단 권고 (이미 만점 구간 도달): " + ", ".join(stops))

st.divider()

# ──────────────────────────────────────────────────────────────────
# 4) Validator 검증 로그
# ──────────────────────────────────────────────────────────────────
st.markdown("#### 🛡️ Validator 검증 로그 (자기교정 루프)")
st.caption("에이전트 출력이 SOP 규칙을 지켰는지 검사한 기록입니다. 검증은 LLM이 아닌 "
           "결정론적 Python이 수행하며, 엔진이 계산한 원본 값과 직접 대조합니다. "
           "문제가 발견되면 해당 부문만 자동으로 다시 실행됩니다.")

validation_log = briefing.get("validation_log", [])
with st.container(border=True):
    if not validation_log:
        st.write("검증 기록이 없습니다.")
    for line in validation_log:
        if line.startswith("[") and "통과" in line:
            st.markdown(f"✅ {line}")
        elif line.startswith("[") and "발견" in line:
            st.markdown(f"⚠️ {line}")
        else:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ {line}", unsafe_allow_html=True)
