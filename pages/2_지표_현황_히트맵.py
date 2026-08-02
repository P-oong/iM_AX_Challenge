"""
② 지표 현황 히트맵 — 상한도달(회색) · 진행(녹색) · 가성비(적색) · 사각지대(주황) 시각화

색상은 '지표 상태'를 나타내므로 데이터 시각화 가이드의 고정 Status Palette를 사용한다
(good/warning/critical + 중립 회색). 저대비 경고색(주황)이 있으므로 범례와 hover에
반드시 텍스트 라벨을 함께 표기해 색만으로 의미를 전달하지 않도록 한다.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from src import benchmarking, feedback_store, scoring_engine
from src.state import get_data, sidebar_controls

st.set_page_config(page_title="지표 현황 히트맵", page_icon="🗺️", layout="wide")
sidebar_controls()

CATEGORY_COLORS = {
    "상한도달": "#898781",  # muted ink (중립 회색)
    "진행": "#0ca30c",      # status good
    "가성비": "#d03b3b",    # status critical
    "사각지대": "#fab219",  # status warning
}
CATEGORY_ICON = {"상한도달": "🔘", "진행": "🟢", "가성비": "🔴", "사각지대": "🟠"}

data = get_data()
computed = scoring_engine.compute_all(data["indicators"])
learned_rules = feedback_store.derive_rules(data["feedback_log"])
adjusted = feedback_store.apply_rules(computed, learned_rules)
bench_by_id = {b["id"]: b for b in benchmarking.benchmark_all(computed)}

st.title("🗺️ 지표 현황 히트맵")
st.caption("각 지표를 부문별로 나열하고, 상태에 따라 색을 다르게 표시합니다. "
           "막대 끝에서 마우스를 올리면 상세 근거를 확인할 수 있습니다.")

legend_cols = st.columns(4)
for col, (cat, color) in zip(legend_cols, CATEGORY_COLORS.items()):
    col.markdown(f"{CATEGORY_ICON[cat]} **{cat}**")

rows = []
for c in adjusted:
    b = bench_by_id.get(c["id"], {})
    rows.append({
        "부문": c["dept"],
        "지표명": c["name"],
        "달성률(%)": c["attainment_pct"],
        "현재점수": c["current_score"],
        "만점": c["max_score"],
        "상태": c["category"],
        "잔여필요": c["gap"],
        "단위": c["unit"],
        "물리적 달성가능": "가능" if c["is_feasible"] else "불가",
        "peer 최고": b.get("peer_top_pct", None),
        "전주대비": c.get("weekly_delta"),
    })
df = pd.DataFrame(rows)

fig = px.bar(
    df, x="달성률(%)", y="지표명", color="상태", facet_row="부문",
    color_discrete_map=CATEGORY_COLORS,
    orientation="h",
    category_orders={"상태": list(CATEGORY_COLORS.keys())},
    hover_data={"부문": True, "현재점수": True, "만점": True, "잔여필요": True,
                "단위": True, "물리적 달성가능": True, "전주대비": True, "달성률(%)": ":.1f"},
    height=1050,
)
fig.add_vline(x=100, line_dash="dash", line_color="#898781", row="all", col="all")
fig.update_yaxes(matches=None, showticklabels=True, title=None)
fig.update_xaxes(range=[0, 155], gridcolor="rgba(137,135,129,0.25)", title="달성률(%)")
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#898781", legend_title_text="지표 상태",
    margin=dict(l=10, r=10, t=40, b=10),
)
for a in fig.layout.annotations:
    a.text = a.text.split("=")[-1]

st.plotly_chart(fig, width="stretch")

with st.expander("📄 표로 보기 (접근성 대안)"):
    st.dataframe(df, width="stretch", hide_index=True)
