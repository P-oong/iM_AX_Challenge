"""
UI 전용 재사용 컴포넌트 모음. 비즈니스 로직 없음 — 계산은 전부 엔진 모듈이 끝낸 값을 받아
보여주기만 한다.

  - AGENT_PROFILES / render_agent_lineup : 부문 전문 에이전트 소개 카드
  - render_indicator_detail              : 지표 1개의 상세 KPI 데이터(구간 배점표·규정) 표시
  - get_staff_list / render_dispatch_section : 주간 브리핑 전 직원 전송(그룹웨어 발송 시뮬레이션)
"""
import random

import pandas as pd
import streamlit as st

from src import rag
from src.kpi_master import get_by_dept

# ──────────────────────────────────────────────────────────────────────
# 부문 전문 에이전트 소개
# ──────────────────────────────────────────────────────────────────────

AGENT_PROFILES = {
    "수신": {
        "icon": "💰",
        "title": "수신 전문 에이전트",
        "coverage": "요구불 평잔 · 청년도약계좌 · ISA · 급여이체 · 정기예금 등",
        "specialty": "평잔 지표의 잔여일수 대비 효과를 계산해, 월말 임박 유치처럼 실익이 낮은 영업을 걸러냅니다.",
    },
    "여신": {
        "icon": "🏠",
        "title": "여신 전문 에이전트",
        "coverage": "가계·기업·신용·사업자대출, 우량자산 비중 등",
        "specialty": "상한 도달 여부를 최우선 점검하고, 취급액 지표와 건전성 지표를 연동해 리스크를 체크합니다.",
    },
    "외환": {
        "icon": "🌏",
        "title": "외환 전문 에이전트",
        "coverage": "환전 · 수출입 거래 · 해외송금 · 수수료 수익 등",
        "specialty": "건수 대비 단가 편차가 큰 특성을 반영해 건수형/수익형 지표의 점수 효율을 비교 판단합니다.",
    },
    "기업연금": {
        "icon": "🏢",
        "title": "기업·연금 전문 에이전트",
        "coverage": "퇴직연금(IRP) · 법인 급여이체 · DC 전환 · 사업장 유치 등",
        "specialty": "리드타임이 긴 특성을 반영해 '이번 주 과제'와 '분기 파이프라인 과제'를 구분해 제안합니다.",
    },
}

SUPERVISOR_PROFILE = {
    "icon": "🧭",
    "title": "Supervisor (총괄 에이전트)",
    "specialty": "4개 부문 안건을 동일 척도(점/건)로 비교하고, 부문 편중 없이 최종 3대 과제를 확정합니다.",
}

VALIDATOR_PROFILE = {
    "icon": "🛡️",
    "title": "Validator (검증기 · LLM 아님)",
    "specialty": "에이전트가 인용한 모든 수치를 연산엔진 원본과 대조합니다. 불일치 발견 시 해당 부문만 자동 재실행됩니다.",
}


def render_agent_lineup(compact: bool = False) -> None:
    """부문 에이전트 4 + Supervisor + Validator 소개 카드를 그린다."""
    cols = st.columns(4)
    for col, (dept, p) in zip(cols, AGENT_PROFILES.items()):
        with col, st.container(border=True):
            st.markdown(f"### {p['icon']}")
            st.markdown(f"**{p['title']}**")
            st.caption(f"담당: {len(get_by_dept(dept))}개 지표 — {p['coverage']}")
            if not compact:
                st.write(p["specialty"])

    c1, c2 = st.columns(2)
    for col, p in ((c1, SUPERVISOR_PROFILE), (c2, VALIDATOR_PROFILE)):
        with col, st.container(border=True):
            st.markdown(f"**{p['icon']} {p['title']}**")
            st.caption(p["specialty"])


# ──────────────────────────────────────────────────────────────────────
# 지표 상세 (구간 배점표 · 평가기준 · 규정 원문)
# ──────────────────────────────────────────────────────────────────────

def render_indicator_detail(ind: dict) -> None:
    """계산이 끝난 지표 dict 하나를 받아 상세 KPI 데이터를 그린다.
    (주간 브리핑 카드의 '상세 보기' 확장판 내용)"""
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재 실적", f"{ind['current_value']}{ind['unit']}",
              f"{ind['weekly_delta']:+.1f} (전주대비)" if ind.get("weekly_delta") is not None else None)
    m2.metric("현재 점수", f"{ind['current_score']} / {ind['max_score']}점")
    if ind["next_hurdle"]:
        m3.metric("다음 구간까지", f"{ind['gap']}{ind['unit']}", f"통과 시 +{ind['score_gain']}점")
    else:
        m3.metric("다음 구간까지", "만점 도달")
    m4.metric("점수 효율(ROI)", f"{ind['roi']:.2f} 점/{ind['unit']}" if ind["roi"] else "—")

    st.progress(min(ind["attainment_pct"], 100.0) / 100.0,
                text=f"만점 대비 달성률 {ind['attainment_pct']}%")

    # 구간 배점표 — 본부가 배포한 계단식 점수 체계를 그대로 보여준다
    rows = []
    for h in ind["hurdles"]:
        reached = ind["current_value"] >= h["threshold"]
        rows.append({
            "구간 기준": f"{h['threshold']}{ind['unit']} 이상",
            "획득 점수": f"{h['score']}점",
            "달성 여부": "✅ 달성" if reached else "⬜ 미달성",
        })
    st.markdown("**구간별 배점표 (본부 평가기준)**")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    # 규정 원문 (RAG 검색)
    chunks = rag.search(ind["name"], top_k=1)
    st.markdown("**세부 평가기준 지침서 원문**")
    if chunks:
        st.info(f"📖 **{chunks[0]['title']}** — {chunks[0]['text']}")
    else:
        st.warning("지침서에서 해당 지표의 규정을 찾지 못했습니다. 규정 확인 필요.")

    if ind.get("guideline"):
        st.caption(f"요약 유의사항: {ind['guideline']}")


# ──────────────────────────────────────────────────────────────────────
# 전 직원 전송 (그룹웨어 메신저 발송 시뮬레이션)
# ──────────────────────────────────────────────────────────────────────

_SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"]
_GIVEN = ["민수", "서연", "지훈", "하은", "도윤", "수빈", "예준", "가은", "시우", "채원"]
_TITLES = ["계장", "대리", "과장", "차장"]


def get_staff_list(seed: int, staff_count: int) -> list[str]:
    """지점 직원 명단(가상)을 시드 기반으로 생성한다. 같은 시드면 항상 같은 명단."""
    rng = random.Random(seed * 7919)
    staff = set()
    while len(staff) < min(staff_count, 12):
        name = rng.choice(_SURNAMES) + rng.choice(_GIVEN) + " " + rng.choice(_TITLES)
        staff.add(name)
    return sorted(staff)


def build_dispatch_message(briefing: dict, as_of: str) -> str:
    """브리핑을 사내 메신저 발송용 텍스트로 조립한다."""
    lines = [f"📢 [주간 KPI 전략 브리핑] {as_of}", ""]
    lines.append(briefing.get("headline", ""))
    lines.append("")
    for i, card in enumerate(briefing.get("cards", []), start=1):
        lines.append(f"{i}. [{card['label']}] {card['indicator_name']}")
        lines.append(f"   {card['message']}")
    lines.append("")
    lines.append("── 창구 안내·규정 유의사항 ──")
    lines.append(briefing.get("regulation_summary", ""))
    lines.append("")
    lines.append("* 본 브리핑은 KPI 전담 에이전트가 생성했으며, 모든 수치는 연산엔진 검증을 통과했습니다.")
    return "\n".join(lines)


def render_dispatch_section(briefing: dict, data: dict) -> None:
    """'브리핑 전 직원 전송' 섹션. 실제 그룹웨어 API 대신 발송 시뮬레이션으로 동작한다."""
    st.markdown("#### 📨 전 직원 전송 (그룹웨어 메신저)")
    st.caption("확정된 브리핑을 그대로 지점 직원들에게 발송해 즉각적인 현장 교육 자료로 씁니다. "
               "별도 툴 접속 없이 매주 아침 메신저로 자동 발송되는 것이 목표이며, 데모에서는 발송을 시뮬레이션합니다.")

    staff = get_staff_list(data["seed"], data["branch_profile"].get("staff_count", 8))
    default_msg = build_dispatch_message(briefing, data["as_of"])

    with st.container(border=True):
        recipients = st.multiselect("받는 사람", staff, default=staff,
                                    help="기본값은 지점 전 직원입니다.")
        message = st.text_area("발송 내용 (수정 가능)", value=default_msg, height=260)

        c1, c2 = st.columns([1, 3])
        send_clicked = c1.button("📤 메신저로 전송", type="primary", width="stretch")
        c2.caption("실제 서비스에서는 그룹웨어 API와 연동됩니다. (데모: 발송 시뮬레이션)")

        if send_clicked:
            if not recipients:
                st.error("받는 사람을 1명 이상 선택해 주세요.")
            else:
                log = st.session_state.get("dispatch_log", [])
                log.append({
                    "date": data["as_of"],
                    "recipients": len(recipients),
                    "preview": message.splitlines()[0] if message else "",
                })
                st.session_state.dispatch_log = log
                st.success(f"✅ 지점 직원 {len(recipients)}명에게 브리핑을 발송했습니다. (시뮬레이션)")
                with st.chat_message("assistant", avatar="📢"):
                    st.text(message if len(message) < 1200 else message[:1200] + "\n…")

    dispatch_log = st.session_state.get("dispatch_log", [])
    if dispatch_log:
        with st.expander(f"발송 이력 ({len(dispatch_log)}건)"):
            df = pd.DataFrame(dispatch_log)
            df.columns = ["발송일", "수신 인원", "내용 미리보기"]
            st.dataframe(df.iloc[::-1], hide_index=True, width="stretch")
