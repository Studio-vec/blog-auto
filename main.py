"""
메인 실행 파일 — 즉시 실행 or 스케줄러 시작.

사용법:
  python main.py                # 스케줄러 시작 (주 3회 임시저장 자동 실행)
  python main.py --draft        # 지금 바로 임시저장 1건
  python main.py --publish      # 지금 바로 공개 발행 1건 (검수 후 수동 실행용)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
from content_generator import generate_post
from config import TISTORY_BLOG_NAME


def run_post(draft: bool = True) -> None:
    mode_label = "임시저장" if draft else "공개 발행"
    print("=" * 50)
    print(f"📝 블로그 포스트 생성 중... ({mode_label} 모드)")

    post = generate_post()
    print(f"✅ 제목: {post['title']}")
    print(f"📍 여행지: {post['topic']['place']}")
    print(f"📸 포토존: {', '.join(post['topic'].get('photo_points', [])[:2])}")

    if not TISTORY_BLOG_NAME:
        print("⚠️  TISTORY_BLOG_NAME 미설정")
        return

    print(f"\n🚀 티스토리 {mode_label} 중...")
    from tistory_poster import post as tistory_post
    result = tistory_post(post["title"], post["body"], post["tags"], draft=draft)
    icon = "📝" if draft else "✅"
    print(f"{icon} 티스토리 {mode_label}: {result['url']}")
    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="여행 블로그 자동 포스팅")
    parser.add_argument("--draft",   action="store_true", help="지금 바로 임시저장 1건")
    parser.add_argument("--publish", action="store_true", help="지금 바로 공개 발행 1건")
    args = parser.parse_args()

    if args.publish:
        run_post(draft=False)
    elif args.draft:
        run_post(draft=True)
    else:
        from scheduler import start
        start()


if __name__ == "__main__":
    main()
