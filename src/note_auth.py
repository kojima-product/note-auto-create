"""note.com認証モジュール - ログイン処理の共通化"""

import os
import random
import time
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv

load_dotenv()

# Chromium version bundled with Playwright updates frequently
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


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
        user_agent=_USER_AGENT,
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


def _human_type(page: Page, selector: str, text: str) -> None:
    """Type text with random delays to mimic human input"""
    element = page.locator(selector)
    element.click()
    time.sleep(0.3)
    for char in text:
        page.keyboard.type(char, delay=random.randint(30, 80))
    time.sleep(0.2)


def _diagnose_login_page(page: Page) -> None:
    """Log diagnostic info about the current login page state"""
    try:
        info = page.evaluate("""() => {
            const result = {};
            // Check for CAPTCHA / reCAPTCHA
            result.hasRecaptcha = !!document.querySelector('iframe[src*="recaptcha"]');
            result.hasCaptchaDiv = !!document.querySelector('[class*="captcha" i], [id*="captcha" i]');
            result.hasTurnstile = !!document.querySelector('iframe[src*="turnstile"]');
            // Check form state
            const form = document.querySelector('form');
            result.hasForm = !!form;
            // Check visible error messages
            const errorEls = document.querySelectorAll('[class*="error" i], [class*="alert" i], [role="alert"]');
            result.errorTexts = Array.from(errorEls).map(e => e.textContent.trim()).filter(t => t.length > 0).slice(0, 3);
            // Check login button state
            const btns = document.querySelectorAll('button');
            result.buttons = Array.from(btns).map(b => ({
                text: b.textContent.trim().substring(0, 30),
                disabled: b.disabled,
                type: b.type
            }));
            result.url = location.href;
            return result;
        }""")
        print(f"  診断情報:")
        print(f"    URL: {info.get('url', '?')}")
        print(f"    reCAPTCHA: {info.get('hasRecaptcha')}, CAPTCHA div: {info.get('hasCaptchaDiv')}, Turnstile: {info.get('hasTurnstile')}")
        print(f"    form要素: {info.get('hasForm')}")
        if info.get('errorTexts'):
            print(f"    エラーメッセージ: {info['errorTexts']}")
        for btn in info.get('buttons', []):
            if 'ログイン' in btn.get('text', ''):
                print(f"    ログインボタン: text='{btn['text']}' disabled={btn['disabled']} type={btn['type']}")
    except Exception as e:
        print(f"  診断情報取得エラー: {e}")


def login(page: Page, email: str = None, password: str = None, max_retries: int = 2) -> bool:
    """Login to note.com with retry

    Args:
        page: Playwright page
        email: note.com email (defaults to NOTE_EMAIL env var)
        password: note.com password (defaults to NOTE_PASSWORD env var)
        max_retries: number of retries on failure

    Returns:
        True if login successful
    """
    email = email or os.getenv("NOTE_EMAIL")
    password = password or os.getenv("NOTE_PASSWORD")

    if not email or not password:
        raise ValueError("NOTE_EMAIL と NOTE_PASSWORD を .env に設定してください")

    LOGIN_URL = "https://note.com/login"

    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"\n  ログインリトライ ({attempt}/{max_retries})...")
            time.sleep(5 + attempt * 3)

        print("ログイン中...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(2)

        page.screenshot(path="debug_login_page.png")
        print("  デバッグ: ログインページのスクリーンショットを保存")

        # Email input - use human-like typing
        try:
            email_input = page.locator('input#email')
            email_input.wait_for(state="visible", timeout=10000)
            email_input.click()
            time.sleep(0.3)
            email_input.fill("")  # clear first
            _human_type(page, 'input#email', email)
            print("  メールアドレス入力完了")
        except Exception as e:
            print(f"  メールアドレス入力エラー: {e}")
            page.screenshot(path="debug_email_error.png")
            continue

        time.sleep(0.5)

        # Password input - use human-like typing
        try:
            password_input = page.locator('input#password')
            password_input.wait_for(state="visible", timeout=10000)
            password_input.click()
            time.sleep(0.3)
            password_input.fill("")  # clear first
            _human_type(page, 'input#password', password)
            print("  パスワード入力完了")
        except Exception as e:
            print(f"  パスワード入力エラー: {e}")
            page.screenshot(path="debug_password_error.png")
            continue

        time.sleep(0.5)

        # Diagnose before clicking login
        _diagnose_login_page(page)

        # Click login button - prefer form submit button
        try:
            # Try specific submit button first
            login_button = page.locator('form button[type="submit"], form button:has-text("ログイン")')
            if login_button.count() == 0:
                login_button = page.locator('button:has-text("ログイン")')
            login_button.first.wait_for(state="visible", timeout=10000)
            login_button.first.click()
            print("  ログインボタンクリック完了")
        except Exception as e:
            print(f"  ログインボタンエラー: {e}")
            page.screenshot(path="debug_login_button_error.png")
            continue

        # Wait for URL to change from login page
        try:
            page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=30000,
            )
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            page.screenshot(path="debug_after_login.png")
            print(f"  ログイン成功（URL遷移）: {page.url}")
            return True
        except Exception:
            pass

        # Fallback: check if URL changed after additional wait
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        current_url = page.url
        if "/login" not in current_url:
            page.screenshot(path="debug_after_login_url_only.png")
            print(f"  ログイン成功（URL判定フォールバック）: {current_url}")
            return True

        # Diagnose failure
        print(f"  ログイン失敗（URL変化なし）: {current_url}")
        _diagnose_login_page(page)
        page.screenshot(path="debug_login_failed.png")

    print("  ログインリトライ上限に達しました")
    return False
