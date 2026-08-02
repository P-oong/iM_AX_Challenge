"""
이미지 자산 로딩 헬퍼 — assets/ 폴더에 정해진 파일명으로 이미지를 넣기만 하면
해당 위치에 자동으로 표시된다. 파일이 없으면 아무것도 표시하지 않으므로(오류 없음),
이미지 없이도 앱은 그대로 동작한다.

지원하는 슬롯 (파일명 → 표시 위치):
  assets/logo.*             → 사이드바 최상단 (모든 페이지 공통)
  assets/hero.*             → 홈(Home.py) 상단 배너
  assets/briefing_banner.*  → ① 주간 전략 브리핑 페이지 상단 배너
  assets/background.*       → 앱 전체 배경 (반투명 오버레이로 가독성 유지)

확장자는 png/jpg/jpeg/webp 를 인식한다. 배너·배경은 용량이 큰 원본 PNG보다
가로 1600px 내외의 JPEG가 로딩 속도에 유리하다.
"""
import base64
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]


def _find(stem: str) -> Path | None:
    """assets/<stem>.<확장자> 중 존재하는 첫 파일을 찾는다."""
    for ext in _EXTENSIONS:
        p = ASSETS_DIR / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def show_banner(stem: str) -> bool:
    """배너 이미지를 전체 폭으로 표시한다. 파일이 없으면 False를 반환하고 아무것도 안 한다."""
    path = _find(stem)
    if path is None:
        return False
    st.image(str(path), width="stretch")
    return True


def sidebar_logo() -> bool:
    """사이드바 상단에 로고를 표시한다."""
    path = _find("logo")
    if path is None:
        return False
    st.sidebar.image(str(path), width="stretch")
    return True


@st.cache_data(show_spinner=False)
def _background_css(path_str: str, mtime: float) -> str:
    """배경 이미지를 base64로 인코딩한 CSS를 만든다.
    위젯 조작마다 스크립트가 통째로 재실행되는 Streamlit 특성상 캐싱하지 않으면
    매 리런마다 이미지를 다시 읽고 인코딩하게 된다. mtime을 키에 넣어 파일을
    교체하면 캐시가 자동으로 무효화되도록 한다."""
    path = Path(path_str)
    b64 = base64.b64encode(path.read_bytes()).decode()
    mime = "jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else path.suffix.lstrip(".").lower()
    return f"data:image/{mime};base64,{b64}"


def apply_background() -> bool:
    """assets/background.* 가 있으면 앱 전체 배경으로 깐다.
    글자 가독성을 위해 흰색 반투명 오버레이를 함께 적용한다."""
    path = _find("background")
    if path is None:
        return False
    data_uri = _background_css(str(path), path.stat().st_mtime)
    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background:
                linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.90)),
                url("{data_uri}") center / cover fixed no-repeat;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    return True
