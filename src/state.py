"""모든 페이지가 공유하는 세션 상태 초기화 및 데이터 로딩 헬퍼.

- seed: 데이터 재현성을 위한 시드값 (사이드바에서 변경 가능)
- feedback_log: 지점장 피드백 누적 로그. 데이터를 재생성해도 유지된다
  (인사이동/실적 갱신과 무관하게 축적되는 '지점 메모리'라는 컨셉을 반영).
"""
import streamlit as st

from src import data_generator


def get_data() -> dict:
    if "seed" not in st.session_state:
        st.session_state.seed = 42

    raw = data_generator.generate_branch_data(seed=st.session_state.seed)

    if "feedback_log" not in st.session_state:
        st.session_state.feedback_log = raw["feedback_log"]

    raw["feedback_log"] = st.session_state.feedback_log
    return raw


def set_seed(seed: int) -> None:
    st.session_state.seed = seed


def append_feedback(entry: dict) -> None:
    st.session_state.feedback_log = st.session_state.feedback_log + [entry]


def sidebar_controls() -> None:
    with st.sidebar:
        st.markdown("### ⚙️ 데모 설정")
        seed = st.number_input("데이터 시드", min_value=0, max_value=9999,
                                value=st.session_state.get("seed", 42), step=1,
                                help="같은 시드를 넣으면 항상 같은 가상 실적 데이터가 재현됩니다.")
        if st.button("🔄 실적 데이터 재생성", width="stretch"):
            set_seed(int(seed))
            st.rerun()
        st.caption("※ 피드백 로그(지점 학습 규칙)는 데이터를 재생성해도 유지됩니다 — "
                   "인사이동과 무관하게 축적되는 지점 메모리 컨셉을 반영합니다.")
        st.divider()
        from src.config import has_openai_api_key
        if has_openai_api_key():
            st.success("OpenAI API 연결됨 — AI 브리핑/Q&A 실사용 중")
        else:
            st.warning("OpenAI API 키 미설정 — 폴백(결정론적 템플릿)으로 동작 중")
