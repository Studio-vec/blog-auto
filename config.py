import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 절대경로로 지정 (어느 디렉토리에서 실행해도 동작)
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

TISTORY_BLOG_NAME = os.getenv("TISTORY_BLOG_NAME", "")
KAKAO_ID = os.getenv("KAKAO_ID", "")
KAKAO_PW = os.getenv("KAKAO_PW", "")

NAVER_ID = os.getenv("NAVER_ID", "")
NAVER_PW = os.getenv("NAVER_PW", "")

POST_DAYS = [d.strip() for d in os.getenv("POST_DAYS", "TUE,FRI").split(",")]
POST_TIME = os.getenv("POST_TIME", "09:00")

DAY_MAP = {
    "MON": "monday", "TUE": "tuesday", "WED": "wednesday",
    "THU": "thursday", "FRI": "friday", "SAT": "saturday", "SUN": "sunday"
}
