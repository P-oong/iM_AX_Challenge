"""
⑤ 피드백 로그 — 누적 보류 사유 → 학습된 지점 고유 규칙 목록

① 주간 전략 브리핑 화면에서 쌓인 [수용/보류] 결정이 여기 누적된다. 동일 (부문, 사유)
조합이 3회 이상 쌓이면 feedback_store가 이를 '지점 고유 규칙'으로 승격시켜, 다음 번
브리핑 생성 시 해당 부문 지표의 추천 우선순위를 자동으로 낮춘다.
"""
import pandas as pd
import streamlit as st

from src import data_generator, feedback_store, theme
from src.state import get_data, sidebar_controls

st.set_page_config(page_title="피드백 로그", page_icon="📝", layout="wide")
theme.apply_background()
sidebar_controls()

data = get_data()
log = data["feedback_log"]
rules = feedback_store.derive_rules(log)

st.title("📝 피드백 로그 · 지점 학습 규칙")

st.markdown("#### 🧠 학습된 지점 고유 규칙")
if rules:
    for r in rules:
        st.success(f"**[{r['dept']}]** {r['rule_text']}")
else:
    st.info(f"아직 학습된 규칙이 없습니다. 동일 (부문·사유) 조합이 "
            f"{feedback_store.RULE_THRESHOLD}회 이상 쌓이면 규칙으로 승격됩니다.")

st.divider()
st.markdown("#### 📜 누적 피드백 이력")
if log:
    df = pd.DataFrame(log)[["date", "dept", "indicator_name", "decision", "reason"]]
    df.columns = ["일자", "부문", "지표명", "결정", "사유"]
    st.dataframe(df.sort_values("일자", ascending=False), width="stretch", hide_index=True)
else:
    st.write("아직 피드백 이력이 없습니다. ① 주간 전략 브리핑 화면에서 [수용/보류] 버튼을 눌러보세요.")

st.divider()
if st.button("🗑️ 피드백 로그 초기화 (시드 데이터로 복원)"):
    st.session_state.feedback_log = data_generator.generate_branch_data(seed=st.session_state.get("seed", 42))["feedback_log"]
    st.rerun()
