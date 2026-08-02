"""
① 주간 전략 브리핑 — 3대 과제 카드 + 규정 요약 박스 + 수용/보류 피드백 버튼

Supervisor Agent가 부문별 연산 결과(가성비/상한도달/벤치마킹/사각지대)를 종합해
지점장에게 보고하는 화면. 지점장이 [수용/보류] 버튼을 누르면 그 결정이 피드백
로그에 쌓이고, ⑤ 피드백 로그 화면에서 학습된 규칙으로 진화한다.
"""
import streamlit as st

from src import benchmarking, feedback_store, llm_agent, rag, scoring_engine
from src.state import append_feedback, get_data, sidebar_controls

st.set_page_config(page_title="주간 전략 브리핑", page_icon="📋", layout="wide")
sidebar_controls()

data = get_data()
computed = scoring_engine.compute_all(data["indicators"])
bench_rows = benchmarking.benchmark_all(computed)
learned_rules = feedback_store.derive_rules(data["feedback_log"])
adjusted = feedback_store.apply_rules(computed, learned_rules)

by_category = {"가성비": [], "상한도달": [], "사각지대": []}
for c in adjusted:
    if c["category"] in by_category:
        by_category[c["category"]].append(c)

top_roi = sorted(by_category["가성비"], key=lambda c: c["adjusted_roi"], reverse=True)[:2]
maxed = by_category["상한도달"][:1]
micro = by_category["사각지대"][:1]
underperforming = benchmarking.top_underperforming(computed, n=1)

related_names = [c["name"] for c in (top_roi + maxed + micro)]
reg_chunks = []
for name in related_names:
    reg_chunks += rag.search(name, top_k=1)
regulation_note = "\n".join(f"[{c['title']}] {c['text'][:150]}" for c in reg_chunks[:3]) or "관련 규정 근거를 찾지 못했습니다."

facts = {
    "top_roi": top_roi,
    "maxed": maxed,
    "underperforming": underperforming,
    "micro": micro,
    "learned_rules": learned_rules,
    "regulation_note": regulation_note,
}

st.title("📋 이번 주 전략 브리핑")
st.caption(f"기준일 {data['as_of']} · 잔여 {data['remaining_days']}영업일 · {data['branch_profile']['type']}")

if st.button("🔄 브리핑 다시 생성", help="AI가 최신 데이터로 브리핑 문구를 새로 생성합니다."):
    st.session_state.pop("briefing", None)

if "briefing" not in st.session_state or st.session_state.get("briefing_seed") != data["seed"]:
    with st.spinner("Supervisor Agent가 브리핑을 작성하는 중..."):
        st.session_state.briefing = llm_agent.generate_weekly_briefing(facts)
        st.session_state.briefing_seed = data["seed"]

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
