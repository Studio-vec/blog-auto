"""
주 3회 임시저장 스케줄러.
POST_DAYS / POST_TIME 환경변수로 요일·시간 설정 (기본: MON,WED,FRI / 09:00).
매주 3건을 임시저장 → 사용자가 2건 선별해 직접 발행.
"""

import schedule
import time
from config import POST_DAYS, POST_TIME, DAY_MAP
from main import run_post


def _register_jobs() -> None:
    for day_key in POST_DAYS:
        day_fn_name = DAY_MAP.get(day_key.upper())
        if not day_fn_name:
            print(f"⚠️  알 수 없는 요일: {day_key} — 건너뜀")
            continue
        job_fn = getattr(schedule.every(), day_fn_name)
        job_fn.at(POST_TIME).do(run_post, draft=True)   # 임시저장 모드 고정
        print(f"✅ 스케줄 등록: 매주 {day_key} {POST_TIME} → 임시저장")


def start() -> None:
    print("🗓️  블로그 자동 저장 스케줄러 시작")
    print("   매주 3건 비공개 발행 → 관리 페이지에서 2건 선택 후 공개로 전환")
    _register_jobs()
    print("대기 중... (Ctrl+C로 종료)\n")
    while True:
        schedule.run_pending()
        time.sleep(30)
