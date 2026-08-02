"""
KPI 지표 마스터 (반기 단위로 배포되는 세부 평가 기준을 코드로 표현)

실제 서비스에서는 본부가 배포하는 엑셀/문서를 파싱해 이 구조로 적재하지만,
데모에서는 손으로 정의한 대표 지표 20여 개로 축소했다.
각 지표는 "계단식 구간 점수 체계"를 hurdles(허들)로 표현한다:
  hurdles = [{"threshold": 건수/금액, "score": 그 구간 통과 시 누적 점수}, ...]
현재값이 특정 허들의 threshold 이상이면 그 허들의 score를 획득 (마지막에 도달한 허들 기준).
"""

DEPARTMENTS = ["수신", "여신", "외환", "기업연금"]

# is_micro: 조건이 복잡해 창구 직원이 놓치기 쉬운 '사각지대' 후보 지표
KPI_MASTER = [
    # ── 수신 Agent ──────────────────────────────────────────────
    {"id": "SU01", "dept": "수신", "name": "요구불 평잔", "unit": "백만원",
     "hurdles": [{"threshold": 500, "score": 2}, {"threshold": 800, "score": 4}, {"threshold": 1200, "score": 7}],
     "guideline": "월말 잔액이 아닌 '일평균 잔액' 기준으로 평가. 월말 막판 유치는 실익이 낮음.",
     "is_micro": False},
    {"id": "SU02", "dept": "수신", "name": "청년도약계좌 신규", "unit": "건",
     "hurdles": [{"threshold": 5, "score": 2}, {"threshold": 10, "score": 5}, {"threshold": 15, "score": 9}],
     "guideline": "실적의 50%만 인정. 가입 당월이 아닌 '익월 말' 잔액 기준으로 평가.",
     "is_micro": False},
    {"id": "SU03", "dept": "수신", "name": "ISA 신규", "unit": "건",
     "hurdles": [{"threshold": 8, "score": 2}, {"threshold": 15, "score": 5}, {"threshold": 22, "score": 8}],
     "guideline": "일임형/신탁형 구분 없이 인정. 타행 이전 계좌는 제외.",
     "is_micro": False},
    {"id": "SU04", "dept": "수신", "name": "급여이체 신규(개인)", "unit": "건",
     "hurdles": [{"threshold": 6, "score": 2}, {"threshold": 12, "score": 4}, {"threshold": 18, "score": 6}],
     "guideline": "3개월 연속 급여 입금 확인 시에만 최종 인정.",
     "is_micro": False},
    {"id": "SU05", "dept": "수신", "name": "입출금 통장 신규 당일 20만원 이상 입금", "unit": "건",
     "hurdles": [{"threshold": 4, "score": 1}, {"threshold": 8, "score": 3}, {"threshold": 12, "score": 5}],
     "guideline": "통장 개설 당일 20만 원 이상 입금 시에만 가점. 익일 입금은 불인정.",
     "is_micro": True},
    {"id": "SU06", "dept": "수신", "name": "자녀 명의 청약저축 신규", "unit": "건",
     "hurdles": [{"threshold": 3, "score": 1}, {"threshold": 6, "score": 3}, {"threshold": 9, "score": 5}],
     "guideline": "미성년자 명의, 법정대리인 동반 개설 건만 인정.",
     "is_micro": True},
    {"id": "SU07", "dept": "수신", "name": "아파트 관리비 자동이체 등록", "unit": "건",
     "hurdles": [{"threshold": 10, "score": 1}, {"threshold": 20, "score": 3}, {"threshold": 30, "score": 5}],
     "guideline": "관리사무소 단체 등록이 아닌 개별 신규 등록 건만 인정.",
     "is_micro": True},

    # ── 여신 Agent ──────────────────────────────────────────────
    {"id": "YS01", "dept": "여신", "name": "가계대출 신규", "unit": "백만원",
     "hurdles": [{"threshold": 300, "score": 3}, {"threshold": 600, "score": 6}, {"threshold": 900, "score": 10}],
     "guideline": "DSR 규제 비율 내 취급 건만 인정. 대환 건은 순증분만 반영.",
     "is_micro": False},
    {"id": "YS02", "dept": "여신", "name": "기업대출 신규", "unit": "백만원",
     "hurdles": [{"threshold": 400, "score": 3}, {"threshold": 700, "score": 6}, {"threshold": 1000, "score": 10}],
     "guideline": "우량기업(신용등급 BBB+ 이상) 취급 시 가중치 1.2배.",
     "is_micro": False},
    {"id": "YS03", "dept": "여신", "name": "우량자산 비중", "unit": "%",
     "hurdles": [{"threshold": 60, "score": 2}, {"threshold": 70, "score": 5}, {"threshold": 80, "score": 8}],
     "guideline": "신용등급 A- 이상 자산의 전체 여신 잔액 대비 비중.",
     "is_micro": False},
    {"id": "YS04", "dept": "여신", "name": "전세자금대출 신규", "unit": "건",
     "hurdles": [{"threshold": 5, "score": 1}, {"threshold": 10, "score": 3}, {"threshold": 15, "score": 5}],
     "guideline": "HUG/HF 보증서 담보 건만 인정.",
     "is_micro": False},
    {"id": "YS05", "dept": "여신", "name": "고정금리 전환 유치", "unit": "건",
     "hurdles": [{"threshold": 4, "score": 1}, {"threshold": 8, "score": 2}, {"threshold": 12, "score": 4}],
     "guideline": "변동금리 기취급 고객의 고정금리 전환만 인정. 신규 취급 제외.",
     "is_micro": True},

    # ── 외환 Agent ──────────────────────────────────────────────
    {"id": "WH01", "dept": "외환", "name": "환전 실적", "unit": "건",
     "hurdles": [{"threshold": 40, "score": 1}, {"threshold": 70, "score": 3}, {"threshold": 100, "score": 5}],
     "guideline": "동일 고객 반복 환전은 최초 1건만 인정.",
     "is_micro": False},
    {"id": "WH02", "dept": "외환", "name": "수출입 거래 취급", "unit": "건",
     "hurdles": [{"threshold": 3, "score": 2}, {"threshold": 6, "score": 5}, {"threshold": 9, "score": 8}],
     "guideline": "L/C 개설·매입 기준. 단순 송금은 제외.",
     "is_micro": False},
    {"id": "WH03", "dept": "외환", "name": "해외송금 신규 고객", "unit": "건",
     "hurdles": [{"threshold": 5, "score": 1}, {"threshold": 10, "score": 2}, {"threshold": 15, "score": 4}],
     "guideline": "최근 6개월 내 거래 이력 없는 고객만 신규로 인정.",
     "is_micro": True},

    # ── 기업·연금 Agent ─────────────────────────────────────────
    {"id": "PN01", "dept": "기업연금", "name": "퇴직연금(IRP) 신규", "unit": "건",
     "hurdles": [{"threshold": 3, "score": 2}, {"threshold": 6, "score": 5}, {"threshold": 9, "score": 9}],
     "guideline": "가입 후 익월까지 최소 1회 이상 납입 확인 시 인정. 리드타임이 길어 분기 단위 관리 필요.",
     "is_micro": False},
    {"id": "PN02", "dept": "기업연금", "name": "법인 급여이체 신규", "unit": "건",
     "hurdles": [{"threshold": 2, "score": 2}, {"threshold": 4, "score": 5}, {"threshold": 6, "score": 9}],
     "guideline": "임직원 5인 이상 법인의 급여이체 전환만 인정. 상권 특성상 B2B 발굴 난도가 높음.",
     "is_micro": False},
    {"id": "PN03", "dept": "기업연금", "name": "DC형 연금 전환", "unit": "건",
     "hurdles": [{"threshold": 2, "score": 1}, {"threshold": 4, "score": 3}, {"threshold": 6, "score": 5}],
     "guideline": "DB형에서 DC형으로 전환하는 기존 가입 법인만 인정.",
     "is_micro": True},
    {"id": "PN04", "dept": "기업연금", "name": "퇴직연금 사업장 유치", "unit": "건",
     "hurdles": [{"threshold": 1, "score": 3}, {"threshold": 2, "score": 7}, {"threshold": 3, "score": 12}],
     "guideline": "신규 사업장 단위 계약 체결 건. 영업 리드타임이 길어 분기 초 착수 권장.",
     "is_micro": False},
]


def get_master():
    return KPI_MASTER


def get_by_dept(dept: str):
    return [k for k in KPI_MASTER if k["dept"] == dept]
