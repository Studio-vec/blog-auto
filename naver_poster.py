"""
Playwright를 이용한 네이버 블로그 자동 포스팅 모듈.
네이버는 공식 글쓰기 API가 없어서 브라우저 자동화를 사용.
"""

import re
import time
from playwright.sync_api import sync_playwright, Page
from config import NAVER_ID, NAVER_PW

NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
NAVER_BLOG_WRITE_URL = "https://blog.naver.com/PostWriteForm.naver"


def _login(page: Page) -> None:
    page.goto(NAVER_LOGIN_URL)
    page.wait_for_load_state("networkidle")

    # 자바스크립트로 입력 (봇 감지 우회)
    page.evaluate(f"document.querySelector('#id').value = '{NAVER_ID}'")
    page.evaluate(f"document.querySelector('#pw').value = '{NAVER_PW}'")
    page.click(".btn_login")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # 추가 인증(캡챠, 전화인증) 발생 시 대기
    if "nidlogin" in page.url or "login" in page.url:
        print("[네이버] 추가 인증이 필요합니다. 60초 안에 브라우저에서 직접 처리해주세요.")
        time.sleep(60)


def _write_post(page: Page, title: str, body_html: str, tags: str) -> str:
    """스마트에디터 ONE 기반 글쓰기."""
    page.goto(f"{NAVER_BLOG_WRITE_URL}?blogId={NAVER_ID}")
    page.wait_for_load_state("networkidle")
    time.sleep(3)

    # iframe 내부 에디터 접근
    title_frame = page.frame_locator("iframe#mainFrame")

    # 제목 입력
    title_input = title_frame.locator(".se-title-input")
    title_input.click()
    title_input.fill(title)
    time.sleep(0.5)

    # 본문: HTML 직접 삽입 (스마트에디터 ONE 내부 ProseMirror 활용)
    editor = title_frame.locator(".se-main-container")
    editor.click()

    # HTML 붙여넣기 방식으로 본문 입력
    plain_text = re.sub(r"<[^>]+>", "", body_html)  # HTML → 플레인텍스트
    page.keyboard.type(plain_text, delay=5)
    time.sleep(1)

    # 태그 입력
    tag_input = title_frame.locator(".se-tag-input input")
    if tag_input.count() > 0:
        for tag in tags.split():
            clean_tag = tag.lstrip("#").strip()
            if clean_tag:
                tag_input.fill(clean_tag)
                page.keyboard.press("Enter")
                time.sleep(0.3)

    # 발행
    publish_btn = title_frame.locator("button.publish-btn, button:has-text('발행')")
    publish_btn.first.click()
    time.sleep(2)

    # 공개 설정 후 최종 발행
    confirm_btn = page.locator("button:has-text('발행'), .btn_publish")
    if confirm_btn.count() > 0:
        confirm_btn.first.click()
        time.sleep(3)

    post_url = page.url
    print(f"[네이버] 포스팅 완료 → {post_url}")
    return post_url


def post(title: str, body_html: str, tags: str) -> dict:
    """네이버 블로그에 글 발행. headless=False 로 실행 (봇 감지 방지)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        try:
            _login(page)
            post_url = _write_post(page, title, body_html, tags)
        finally:
            browser.close()

    return {"url": post_url}
