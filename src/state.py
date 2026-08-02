"""모든 페이지가 공유하는 세션 상태 초기화 및 데이터 로딩 헬퍼.

- seed: 데이터 재현성을 위한 시드값 (사이드바에서 변경 가능)
- as_of_date: 데이터를 생성하는 기준일. 월초에는 "이번 달 히스토리"가 짧아
  전주대비 비교가 불가능하므로, 시연 시 월 중순 이후 날짜로 조정할 수 있게 한다.
- feedback_log: 지점장 피드백 누적 로그. 데이터를 재생성해도 유지된다
  (인사이동/실적 갱신과 무관하게 축적되는 '지점 메모리'라는 컨셉을 반영).
"""
from datetime import date

import streamlit as st

from src import data_generator


def get_data() -> dict:
    if "seed" not in st.session_state:
        st.session_state.seed = 42
    if "as_of_date" not in st.session_state:
        st.session_state.as_of_date = date.today()

    raw = data_generator.generate_branch_data(seed=st.session_state.seed, today=st.session_state.as_of_date)

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
        as_of = st.date_input(
            "기준일 (데모용)", value=st.session_state.get("as_of_date", date.today()),
            help="월초에는 이번 달 실적 히스토리가 짧아 '전주대비' 비교가 표시되지 않습니다. "
                 "전주대비 변화를 보여주려면 월 중순 이후 날짜를 선택하세요.",
        )
        if st.button("🔄 실적 데이터 재생성", width="stretch"):
            set_seed(int(seed))
            st.session_state.as_of_date = as_of
            st.rerun()
        st.caption("※ 피드백 로그(지점 학습 규칙)는 데이터를 재생성해도 유지됩니다 — "
                   "인사이동과 무관하게 축적되는 지점 메모리 컨셉을 반영합니다.")
        st.divider()
        from src.config import has_openai_api_key
        if has_openai_api_key():
            st.success("OpenAI API 연결됨 — AI 브리핑/Q&A 실사용 중")
        else:
            st.warning("OpenAI API 키 미설정 — 폴백(결정론적 템플릿)으로 동작 중")
