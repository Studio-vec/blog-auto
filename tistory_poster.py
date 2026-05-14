"""
Playwright를 이용한 티스토리 자동 포스팅 모듈.
- draft=True  → 임시저장 (기본값, 검수 후 직접 발행)
- draft=False → 즉시 공개 발행
"""

import os
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, BrowserContext

# GitHub Actions 등 CI 환경에서는 headless 모드로 실행
IS_CI = os.getenv("CI", "false").lower() == "true"

SESSION_FILE = Path(__file__).parent / "tistory_session"


def _get_blog_name() -> str:
    from config import TISTORY_BLOG_NAME as BN
    return BN


def _make_context(p, storage_state: str | None = None):
    kwargs = dict(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
    )
    if storage_state:
        kwargs["storage_state"] = storage_state

    browser = p.chromium.launch(
        headless=IS_CI,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    return browser, browser.new_context(**kwargs)


# ── 로그인 ────────────────────────────────────────────────────────────────

def _kakao_login(page: Page) -> None:
    from config import KAKAO_ID, KAKAO_PW

    print("[티스토리] 카카오 로그인 시도...")
    kakao_btn = page.locator(
        "a.link_kakao_id, a.btn_kakao_id, "
        "a[href*='kakao.com'], a[href*='accounts.kakao'], "
        "a:has-text('카카오계정으로 로그인'), button:has-text('카카오계정으로 로그인')"
    )
    if kakao_btn.count() > 0:
        kakao_btn.first.click(timeout=10000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

    page.wait_for_load_state("networkidle")
    time.sleep(2)

    try:
        id_input = page.wait_for_selector(
            "#loginKey, input[name='loginKey'], input[type='email'], "
            "input[placeholder*='이메일'], input[placeholder*='전화번호']",
            timeout=10000,
        )
        id_input.click()
        id_input.fill(KAKAO_ID)
        time.sleep(0.5)
    except Exception as e:
        print(f"[티스토리] ID 입력란 못 찾음: {e}")

    try:
        pw_input = page.wait_for_selector(
            "#password, input[name='password'], input[type='password']",
            timeout=5000,
        )
        pw_input.click()
        pw_input.fill(KAKAO_PW)
        time.sleep(0.5)
    except Exception as e:
        print(f"[티스토리] PW 입력란 못 찾음: {e}")

    try:
        login_btn = page.wait_for_selector(
            "button[type='submit'], .btn_g.highlight, button.btn_confirm",
            timeout=5000,
        )
        login_btn.click()
        time.sleep(2)
    except Exception:
        page.keyboard.press("Enter")
        time.sleep(2)

    for _ in range(5):
        url = page.url
        if "tistory.com" in url and "auth/login" not in url and "kakao" not in url:
            break
        agree_btn = page.locator("button:has-text('동의'), button:has-text('확인'), button:has-text('계속')")
        if agree_btn.count() > 0:
            try:
                agree_btn.first.click(timeout=3000)
                time.sleep(2)
            except Exception:
                pass
        time.sleep(2)

    print("[티스토리] 로그인 처리 중... (2FA가 있으면 화면에서 직접 완료해주세요)")
    for _ in range(90):
        time.sleep(1)
        url = page.url
        if "tistory.com" in url and "auth/login" not in url and "kakao" not in url:
            break
    else:
        raise RuntimeError(f"카카오 로그인 실패 — 현재 URL: {page.url}")

    print("[티스토리] 카카오 로그인 완료 ✅")


def _auto_login(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.goto("https://www.tistory.com/auth/login")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        _kakao_login(page)
        time.sleep(2)
        context.storage_state(path=str(SESSION_FILE))
        print("[티스토리] 세션 저장 완료 ✅")
    finally:
        page.close()


# ── 내용 입력 (공통) ───────────────────────────────────────────────────────

def _fill_content(page: Page, title: str, body_html: str, tags: str) -> None:
    blog_name = _get_blog_name()
    write_url = f"https://{blog_name}.tistory.com/manage/post/"
    page.goto(write_url)
    page.wait_for_load_state("networkidle")
    time.sleep(5)

    if "auth/login" in page.url:
        SESSION_FILE.unlink(missing_ok=True)
        raise RuntimeError("세션 만료. 다시 실행하면 재로그인합니다.")

    # 제목
    try:
        title_el = page.wait_for_selector(
            "#post-title-inp, textarea.textarea_tit", timeout=10000
        )
        title_el.click()
        title_el.fill(title)
        print(f"[티스토리] 제목 입력: {title[:40]}...")
    except Exception as e:
        print(f"[티스토리] 제목 입력 실패: {e}")

    time.sleep(1)

    # 본문 (TinyMCE)
    for _ in range(20):
        ready = page.evaluate(
            "() => typeof tinyMCE !== 'undefined' && "
            "tinyMCE.activeEditor !== null && "
            "tinyMCE.activeEditor.initialized"
        )
        if ready:
            break
        time.sleep(0.5)

    try:
        page.evaluate(
            "(html) => { if (typeof tinyMCE !== 'undefined' && tinyMCE.activeEditor) {"
            "  tinyMCE.activeEditor.setContent(html);"
            "  tinyMCE.activeEditor.save();"   # textarea(#editor-tistory)에 동기화
            "} }",
            body_html[:10000],
        )
        # 동기화 확인
        content_len = page.evaluate(
            "() => (document.querySelector('#editor-tistory') || {}).value?.length || 0"
        )
        print(f"[티스토리] 본문 입력 완료 (textarea 동기화: {content_len}자)")
    except Exception as e:
        print(f"[티스토리] 본문 입력 실패: {e}")

    time.sleep(1)

    # 태그
    try:
        tag_input = page.wait_for_selector(
            "#tagText, input[name='tagText'], input[placeholder*='태그']",
            timeout=5000,
        )
        for tag in tags.split()[:10]:
            clean = tag.lstrip("#").strip()
            if clean and re.match(r"[가-힣A-Za-z0-9]", clean):
                try:
                    tag_input.fill(clean)
                    page.keyboard.press("Enter")
                    time.sleep(0.3)
                except Exception:
                    pass
    except Exception as e:
        print(f"[티스토리] 태그 입력 실패: {e}")

    time.sleep(0.5)


# ── 발행 (공개 / 비공개) ──────────────────────────────────────────────────

def _open_publish_layer(page: Page) -> None:
    """완료 버튼 클릭 → 발행 레이어 오픈."""
    try:
        pub_btn = page.wait_for_selector("#publish-layer-btn", timeout=5000)
        pub_btn.click()
        time.sleep(2)
    except Exception as e:
        raise RuntimeError(f"발행 레이어 오픈 실패: {e}")


def _set_visibility(page: Page, public: bool) -> None:
    """발행 레이어에서 공개/비공개 라디오 버튼 선택."""
    radio_id = "open20" if public else "open0"   # open20=공개, open0=비공개
    try:
        radio = page.wait_for_selector(f"#{radio_id}", timeout=5000)
        radio.click()
        time.sleep(0.5)
        label = "공개" if public else "비공개"
        print(f"[티스토리] 공개 범위: {label}")
    except Exception as e:
        print(f"[티스토리] 공개 범위 설정 실패: {e}")


def _click_publish_confirm(page: Page) -> None:
    """'블로그에 발행' 버튼 클릭."""
    try:
        btn = page.wait_for_selector(
            ".ReactModal__Content #publish-btn, .editor_layer #publish-btn, #publish-btn",
            timeout=5000,
        )
        btn.click()
        time.sleep(4)
    except Exception as e:
        raise RuntimeError(f"발행 버튼 클릭 실패: {e}")


def _latest_post_url(page: Page, blog_name: str, private: bool = False) -> str:
    """발행 후 가장 최근 글 URL 가져오기."""
    status = "0" if private else ""
    list_url = f"https://{blog_name}.tistory.com/manage/posts/" + (f"?status={status}" if status else "")
    try:
        page.goto(list_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        first = page.locator("a[href*='manage/post/'][href*='postId']").first
        if first.count() > 0:
            href = first.get_attribute("href") or ""
            m = re.search(r"postId=(\d+)", href)
            if m:
                return f"https://{blog_name}.tistory.com/{m.group(1)}"
    except Exception:
        pass
    return list_url


def _do_draft(page: Page) -> str:
    """비공개로 발행 → 검수용 임시 보관함 역할."""
    blog_name = _get_blog_name()
    _open_publish_layer(page)
    _set_visibility(page, public=False)   # 비공개
    _click_publish_confirm(page)
    url = _latest_post_url(page, blog_name, private=True)
    print(f"[티스토리] 비공개 저장 완료 → {url}")
    return url


def _do_publish(page: Page) -> str:
    """공개 발행."""
    blog_name = _get_blog_name()
    _open_publish_layer(page)
    _set_visibility(page, public=True)    # 공개
    _click_publish_confirm(page)
    url = _latest_post_url(page, blog_name, private=False)
    print(f"[티스토리] 공개 발행 완료 → {url}")
    return url


# ── 공개 엔트리포인트 ─────────────────────────────────────────────────────

def post(title: str, body_html: str, tags: str, draft: bool = True) -> dict:
    """
    티스토리에 글 저장.
    draft=True  → 임시저장 (기본값)
    draft=False → 즉시 공개 발행
    """
    with sync_playwright() as p:
        if SESSION_FILE.exists():
            print("[티스토리] 저장된 세션으로 로그인")
            browser, context = _make_context(p, storage_state=str(SESSION_FILE))
        else:
            print("[티스토리] 세션 없음 → 카카오 자동 로그인")
            browser, context = _make_context(p)
            _auto_login(context)

        page = context.new_page()
        try:
            _fill_content(page, title, body_html, tags)

            if draft:
                url = _do_draft(page)
                mode = "임시저장"
            else:
                url = _do_publish(page)
                mode = "발행"

            context.storage_state(path=str(SESSION_FILE))
        except RuntimeError as e:
            if "세션 만료" in str(e):
                SESSION_FILE.unlink(missing_ok=True)
            raise
        finally:
            browser.close()

    print(f"[티스토리] {mode} 완료 → {url}")
    return {"url": url, "mode": mode}
