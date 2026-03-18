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
        page.wait_for_url("**/", timeout=30000)
        time.sleep(3)
        page.screenshot(path="debug_after_login.png")
        print("  ログイン後のスクリーンショットを保存")
        return True
    except Exception as e:
        print(f"  ログイン後の画面遷移エラー: {e}")
        page.screenshot(path="debug_login_failed.png")
        return False
