"""
④ 규정 Q&A 챗 — 자연어 질의 → 답변 + 출처 표기, 근거 없는 할루시네이션 억제

rag.py가 규정 지침서(docs/kpi_guideline.md)에서 관련 청크를 찾고, 그 청크가 없으면
LLM을 호출하지 않고 곧바로 "규정 확인 필요"를 반환한다 — 출처 없는 답변을 원천 차단.
"""
import streamlit as st

from src import llm_agent, rag, theme
from src.state import sidebar_controls

st.set_page_config(page_title="규정 Q&A 챗", page_icon="💬", layout="wide")
theme.apply_background()
sidebar_controls()

st.title("💬 KPI 규정 Q&A 챗")
st.caption("예: '청년도약계좌는 언제 기준으로 평가돼?', '입출금 통장 당일 입금 조건이 뭐야?'")

if "qa_history" not in st.session_state:
    st.session_state.qa_history = []

for turn in st.session_state.qa_history:
    with st.chat_message(turn["role"]):
        st.write(turn["content"])
        if turn.get("sources"):
            with st.expander("근거 발췌 보기"):
                for s in turn["sources"]:
                    st.markdown(f"**{s['title']}**  \n{s['text']}")

question = st.chat_input("규정에 대해 질문해 보세요")
if question:
    st.session_state.qa_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    chunks = rag.search(question, top_k=3)
    with st.chat_message("assistant"):
        with st.spinner("규정을 검색하는 중..."):
            answer = llm_agent.answer_regulation_question(question, chunks)
        st.write(answer)
        if chunks:
            with st.expander("근거 발췌 보기"):
                for c in chunks:
                    st.markdown(f"**{c['title']}**  \n{c['text']}")

    st.session_state.qa_history.append({"role": "assistant", "content": answer, "sources": chunks})

if st.button("대화 초기화"):
    st.session_state.qa_history = []
    st.rerun()
