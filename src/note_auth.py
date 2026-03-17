"""note.com認証モジュール - ログイン処理の共通化"""

import os
import time
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv

load_dotenv()


def create_browser_context(playwright, headless: bool = False) -> tuple[Browser, BrowserContext]:
    """Anti-bot detection settings applied browser context"""
    browser = playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="ja-JP",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    return browser, context


def setup_page(context: BrowserContext) -> Page:
    """Create a page with webdriver property removed"""
    page = context.new_page()
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    return page


def login(page: Page, email: str = None, password: str = None) -> bool:
    """Login to note.com

    Args:
        page: Playwright page
        email: note.com email (defaults to NOTE_EMAIL env var)
        password: note.com password (defaults to NOTE_PASSWORD env var)

    Returns:
        True if login successful
    """
    email = email or os.getenv("NOTE_EMAIL")
    password = password or os.getenv("NOTE_PASSWORD")

    if not email or not password:
        raise ValueError("NOTE_EMAIL と NOTE_PASSWORD を .env に設定してください")

    LOGIN_URL = "https://note.com/login"

    print("ログイン中...")
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(3)

    page.screenshot(path="debug_login_page.png")
    print("  デバッグ: ログインページのスクリーンショットを保存")

    # Email input
    try:
        email_input = page.locator('input#email')
        email_input.wait_for(state="visible", timeout=10000)
        email_input.fill(email)
        print("  メールアドレス入力完了")
    except Exception as e:
        print(f"  メールアドレス入力エラー: {e}")
        page.screenshot(path="debug_email_error.png")
        return False

    # Password input
    try:
        password_input = page.locator('input#password')
        password_input.wait_for(state="visible", timeout=10000)
        password_input.fill(password)
        print("  パスワード入力完了")
    except Exception as e:
        print(f"  パスワード入力エラー: {e}")
        page.screenshot(path="debug_password_error.png")
        return False

    # Click login button
    try:
        login_button = page.locator('button:has-text("ログイン")')
        login_button.wait_for(state="visible", timeout=10000)
        login_button.click()
        print("  ログインボタンクリック完了")
    except Exception as e:
        print(f"  ログインボタンエラー: {e}")
        page.screenshot(path="debug_login_button_error.png")
        return False

    try:
        # note側のUI/遷移遅延に備えて、URL固定ではなくログイン離脱を判定する
        page.wait_for_url(lambda url: "note.com/login" not in url, timeout=45000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        page.screenshot(path="debug_after_login.png")
        print(f"  ログイン成功（URL遷移）: {page.url}")
        return True
    except Exception as e:
        print(f"  ログイン後のURL遷移待機がタイムアウト: {e}")

        # フォールバック: URLが変わらなくても、ログイン済みUIが出ていれば成功扱い
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        current_url = page.url
        if "note.com/login" not in current_url:
            page.screenshot(path="debug_after_login_url_only.png")
            print(f"  ログイン成功（URL判定フォールバック）: {current_url}")
            return True

        # よくあるログイン失敗メッセージを検知
        error_selectors = [
            'text="メールアドレスまたはパスワードが違います"',
            'text="ログインに失敗しました"',
            'text="認証に失敗"',
        ]
        for sel in error_selectors:
            try:
                if page.locator(sel).first.is_visible():
                    print(f"  ログイン失敗メッセージを検知: {sel}")
                    page.screenshot(path="debug_login_failed_message.png")
                    return False
            except Exception:
                continue

        page.screenshot(path="debug_login_failed.png")
        return False
