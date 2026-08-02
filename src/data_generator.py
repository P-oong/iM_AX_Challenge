"""
필수 데이터 생성 모듈.

실제로는 KPI 실적 DW(일 단위 배치)와 지점 프로파일 테이블에서 가져올 데이터를,
데모에서는 seed 기반 랜덤 생성으로 대체한다. 생성되는 데이터는:
  1) branch_profile : 당점(우리 지점)의 상권 유형 / 규모 등급 / 직원 수 / 지난 분기 KPI 등급
  2) indicators      : KPI_MASTER 각 지표별 '현재 실적' 스냅샷 + 이번 달 일자별 히스토리 + peer 비교치
  3) feedback_log    : 지점장 피드백 이력(시드 데이터 몇 건 포함 - 데모 몰입감용)

같은 seed를 주면 항상 같은 데이터가 나오도록 결정론적으로 만든다(재현성 검증용).
"""
import random
from datetime import date, timedelta

from src.kpi_master import KPI_MASTER

BRANCH_PROFILES = [
    {"type": "주거단지 밀집 상권", "scale": "중형", "desc": "아파트·주거단지 위주, 가족 단위 고객 비중이 높음"},
    {"type": "오피스·상업 상권", "scale": "대형", "desc": "법인·직장인 고객 비중이 높음"},
    {"type": "공단·산업단지 상권", "scale": "중형", "desc": "제조업 법인 고객 비중이 높음"},
]

PEER_BRANCH_NAMES = ["행복동지점", "미래로지점", "중앙로지점", "한빛지점"]

KPI_GRADES = ["S", "A", "B+", "B", "C"]

# 최근 1주(영업일 5일) 대비 변화를 계산하기 위한 기준 영업일 수
WEEKLY_LOOKBACK_DAYS = 5


def _business_days_left_in_month(today: date) -> int:
    """이번 달 잔여 영업일(주말 제외) 계산."""
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    days = 0
    d = today
    while d < next_month:
        if d.weekday() < 5:  # 0=월 ... 4=금
            days += 1
        d += timedelta(days=1)
    return max(days, 1)


def _business_days_elapsed_in_month(today: date) -> list[date]:
    """이번 달 1일부터 오늘까지의 영업일 목록(주말 제외, 오늘 포함)."""
    month_start = date(today.year, today.month, 1)
    days = []
    d = month_start
    while d <= today:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _generate_history(rng: random.Random, current_value: float, business_days: list[date]) -> list[dict]:
    """이번 달 영업일별 누적 실적 히스토리를 생성한다. 하루하루 증가폭은 들쭉날쭉하게
    무작위 생성하되, 합계가 정확히 current_value(오늘 실적)가 되도록 스케일을 맞춘다."""
    n = len(business_days)
    if n == 0:
        return []
    if current_value <= 0:
        return [{"date": d.isoformat(), "value": 0.0} for d in business_days]

    raw_increments = [rng.uniform(0.3, 1.7) for _ in range(n)]
    scale = current_value / sum(raw_increments)

    history = []
    cumulative = 0.0
    for d, raw in zip(business_days, raw_increments):
        cumulative += raw * scale
        history.append({"date": d.isoformat(), "value": round(cumulative, 1)})
    history[-1]["value"] = round(current_value, 1)  # 부동소수 오차 보정
    return history


def _weekly_comparison(history: list[dict], current_value: float) -> tuple[float | None, float | None]:
    """영업일 기준 1주 전 실적과 현재 실적의 차이를 계산한다.
    이번 달 영업일이 아직 1주 미만이면 비교 대상이 없으므로 None을 반환한다."""
    n = len(history)
    if n <= WEEKLY_LOOKBACK_DAYS:
        return None, None
    value_last_week = history[n - 1 - WEEKLY_LOOKBACK_DAYS]["value"]
    return value_last_week, round(current_value - value_last_week, 1)


def generate_branch_data(seed: int = 42, today: date | None = None) -> dict:
    rng = random.Random(seed)
    today = today or date.today()
    remaining_days = _business_days_left_in_month(today)

    branch_profile = dict(rng.choice(BRANCH_PROFILES))
    branch_profile["name"] = "당점(OO지점)"
    branch_profile["staff_count"] = rng.randint(6, 18)
    branch_profile["prior_quarter_grade"] = rng.choice(KPI_GRADES)

    business_days = _business_days_elapsed_in_month(today)
    indicators = []
    for k in KPI_MASTER:
        last_threshold = k["hurdles"][-1]["threshold"]

        # 상권 특성 반영: 기업연금(B2B)은 주거단지 상권에서 달성률을 낮게 생성
        attain_bias = 1.0
        if k["dept"] == "기업연금" and branch_profile["type"] == "주거단지 밀집 상권":
            attain_bias = 0.45
        elif k["is_micro"]:
            attain_bias = rng.uniform(0.45, 0.75)  # 사각지대 후보: 애매하게 놓친 상태로 생성
        else:
            attain_bias = rng.uniform(0.35, 1.35)  # 일부는 상한 초과(=이미 만점) 하도록

        current_value = round(last_threshold * attain_bias * rng.uniform(0.85, 1.15), 1)
        current_value = max(current_value, 0)

        # 일평균 처리 속도 (건/일 또는 백만원/일 단위) — 잔여기간 내 달성 가능성 판단용
        daily_rate = round((last_threshold / 25) * rng.uniform(0.4, 1.3), 2)

        # peer 지점 3~4곳의 동일 지표 실적(달성률 %) — 벤치마킹용
        peer_attain_pcts = [round(rng.uniform(30, 130), 1) for _ in PEER_BRANCH_NAMES]
        peer_records = list(zip(PEER_BRANCH_NAMES, peer_attain_pcts))

        history = _generate_history(rng, current_value, business_days)
        value_last_week, weekly_delta = _weekly_comparison(history, current_value)

        indicators.append({
            **k,
            "current_value": current_value,
            "daily_rate": daily_rate,
            "remaining_days": remaining_days,
            "peer_records": peer_records,  # [(지점명, 달성률%), ...]
            "history": history,  # 이번 달 영업일별 누적 실적 [{"date":..., "value":...}, ...]
            "value_last_week": value_last_week,  # 영업일 기준 1주 전 실적 (히스토리 부족 시 None)
            "weekly_delta": weekly_delta,  # 1주 전 대비 증감분 (히스토리 부족 시 None)
        })

    feedback_log = _seed_feedback_log(rng)

    return {
        "branch_profile": branch_profile,
        "indicators": indicators,
        "feedback_log": feedback_log,
        "as_of": today.isoformat(),
        "remaining_days": remaining_days,
        "seed": seed,
    }


def _seed_feedback_log(rng: random.Random) -> list[dict]:
    """데모 몰입감을 위한 초기 피드백 이력 시드 데이터.
    '기업연금 Agent'가 제안한 B2B 지표를 지점장이 반복적으로 보류한 상황을 재현하여
    기능3(지점 특화 진화)이 바로 시연 가능하도록 한다."""
    reasons = ["상권부적합", "인력부족", "고객군불일치"]
    seed_entries = []
    base_date = date.today() - timedelta(days=20)
    for i in range(3):
        seed_entries.append({
            "date": (base_date + timedelta(days=i * 6)).isoformat(),
            "dept": "기업연금",
            "indicator_id": "PN02",
            "indicator_name": "법인 급여이체 신규",
            "decision": "보류",
            "reason": rng.choice(reasons[:1] * 3),  # 초기 시드는 '상권부적합'으로 고정해 규칙 학습을 보여줌
        })
    return seed_entries
