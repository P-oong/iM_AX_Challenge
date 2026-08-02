"""
유사그룹(Peer) 벤치마킹 도구.

보고서의 '입체적 데이터 분석관' 기능 중 B) 유사 그룹 벤치마킹을 담당한다.
우리 지점의 달성률과 peer 지점들의 달성률을 비교해 뒤처지는 지표를 찾아낸다.
(peer 데이터는 data_generator에서 생성한 시뮬레이션 값이며, 실제로는 본부 DW의
 유사 상권 그룹 실적 분포를 사용한다.)
"""

GAP_ALERT_THRESHOLD = 25.0  # peer 최고 달성률과의 격차(%p)가 이 값 이상이면 경고 대상


def benchmark_indicator(computed_ind: dict) -> dict:
    peer_records = computed_ind.get("peer_records", [])
    peer_pcts = [p for _, p in peer_records]
    peer_avg = round(sum(peer_pcts) / len(peer_pcts), 1) if peer_pcts else 0.0
    peer_top_name, peer_top_pct = max(peer_records, key=lambda p: p[1]) if peer_records else (None, 0.0)

    my_pct = computed_ind["attainment_pct"]
    gap_to_top = round(peer_top_pct - my_pct, 1)

    return {
        "id": computed_ind["id"],
        "name": computed_ind["name"],
        "dept": computed_ind["dept"],
        "my_pct": my_pct,
        "peer_avg_pct": peer_avg,
        "peer_top_name": peer_top_name,
        "peer_top_pct": peer_top_pct,
        "gap_to_top": gap_to_top,
        "underperforming": gap_to_top >= GAP_ALERT_THRESHOLD,
    }


def benchmark_all(computed_indicators: list[dict]) -> list[dict]:
    rows = [benchmark_indicator(c) for c in computed_indicators]
    return sorted(rows, key=lambda r: r["gap_to_top"], reverse=True)


def top_underperforming(computed_indicators: list[dict], n: int = 1) -> list[dict]:
    rows = [r for r in benchmark_all(computed_indicators) if r["underperforming"]]
    return rows[:n]
