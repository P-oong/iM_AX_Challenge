"""
연산엔진 결과를 부문별로 쪼개 각 전문 에이전트에게 넘길 입력(facts)을 만든다.

이 파일에는 LLM 호출이 전혀 없다. 순수하게 "이미 계산된 숫자"를 부문별로 분류하고
LLM이 읽기 좋은 형태로 추리는 역할만 한다 — '판단은 AI가, 계산은 엔진이' 원칙에서
계산 쪽에 속한다. Phase 3에서 LangGraph를 도입하면 이 함수가 Supervisor 노드의
'과제 분배' 단계가 된다.
"""

from src import benchmarking, rag

# 각 부문 에이전트에게 넘길 지표 개수 상한 — 컨텍스트를 적정 수준으로 유지한다.
MAX_INDICATORS_PER_DEPT = 8


def _slim(ind: dict) -> dict:
    """LLM에게 넘길 필드만 추린다. peer_records/history 원본처럼 길고 해석에
    직접 쓰이지 않는 필드는 제외해 프롬프트를 가볍게 유지한다."""
    return {
        "지표명": ind["name"],
        "단위": ind["unit"],
        "현재실적": ind["current_value"],
        "현재점수": ind["current_score"],
        "만점": ind["max_score"],
        "달성률(%)": ind["attainment_pct"],
        "다음구간까지_필요실적": ind["gap"],
        "다음구간_통과시_추가점수": ind["score_gain"],
        "건당점수효율(ROI)": ind["roi"],
        "잔여기간내_달성가능": ind["is_feasible"],
        "잔여영업일": ind["remaining_days"],
        "상한도달": ind["is_maxed"],
        "상태분류": ind["category"],
        "전주대비증감": ind.get("weekly_delta"),
        "규정요약": ind.get("guideline", ""),
    }


def build_dept_facts(
    dept: str,
    adjusted_indicators: list[dict],
    bench_rows: list[dict],
    learned_rules: list[dict],
    branch_profile: dict,
) -> dict:
    """한 부문에 대한 에이전트 입력을 조립한다.

    adjusted_indicators: feedback_store.apply_rules()를 거친 전체 지표 목록
    bench_rows:          benchmarking.benchmark_all() 결과 (전체)
    learned_rules:       feedback_store.derive_rules() 결과 (전체)
    """
    dept_inds = [i for i in adjusted_indicators if i["dept"] == dept]

    # 추천 후보: 상한 미도달 + 달성 가능한 지표를 조정 ROI 순으로. 부족하면 나머지로 채운다.
    candidates = [i for i in dept_inds if not i["is_maxed"] and i["is_feasible"]]
    candidates.sort(key=lambda i: i.get("adjusted_roi", i["roi"]), reverse=True)
    others = [i for i in dept_inds if i not in candidates]
    selected = (candidates + others)[:MAX_INDICATORS_PER_DEPT]

    maxed = [i for i in dept_inds if i["is_maxed"]]

    # 이 부문에서 peer 대비 뒤처진 지표
    dept_bench = [b for b in bench_rows if b["dept"] == dept and b["underperforming"]]

    # 이 부문에 적용되는 학습 규칙만 추림
    dept_rules = [r for r in learned_rules if r["dept"] == dept]

    # 선정된 지표들의 규정 근거를 RAG로 미리 찾아 첨부 (에이전트가 근거 없이 답하지 않도록)
    reg_chunks = []
    seen_titles = set()
    for ind in selected[:4]:
        for chunk in rag.search(ind["name"], top_k=1):
            if chunk["title"] not in seen_titles:
                seen_titles.add(chunk["title"])
                reg_chunks.append({"제목": chunk["title"], "내용": chunk["text"]})

    return {
        "dept": dept,
        "branch_profile": {
            "상권유형": branch_profile["type"],
            "규모": branch_profile["scale"],
            "직원수": branch_profile.get("staff_count"),
            "지난분기등급": branch_profile.get("prior_quarter_grade"),
        },
        "indicators": [_slim(i) for i in selected],
        "maxed_indicators": [i["name"] for i in maxed],
        "benchmark_gaps": [
            {
                "지표명": b["name"],
                "당점달성률(%)": b["my_pct"],
                "최우수지점": b["peer_top_name"],
                "최우수지점달성률(%)": b["peer_top_pct"],
                "격차(%p)": b["gap_to_top"],
            }
            for b in dept_bench[:2]
        ],
        "learned_rules": [r["rule_text"] for r in dept_rules],
        "regulation_excerpts": reg_chunks,
    }


def build_all_dept_facts(
    departments: list[str],
    adjusted_indicators: list[dict],
    computed_indicators: list[dict],
    learned_rules: list[dict],
    branch_profile: dict,
) -> dict[str, dict]:
    """모든 부문에 대한 에이전트 입력을 한 번에 만든다.
    Phase 3에서는 이 결과가 LangGraph의 fan-out 입력이 된다."""
    bench_rows = benchmarking.benchmark_all(computed_indicators)
    return {
        dept: build_dept_facts(dept, adjusted_indicators, bench_rows, learned_rules, branch_profile)
        for dept in departments
    }
