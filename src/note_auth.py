"""note.com認証モジュール - Cookie永続化によるreCAPTCHA回避"""

import base64
import json
import os
import random
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv

load_dotenv()

# Chromium version bundled with Playwright updates frequently
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_SESSION_FILE = Path(__file__).parent.parent / ".auth" / "note_session.json"


def create_browser_context(
    playwright, headless: bool = False, use_session: bool = True
) -> tuple[Browser, BrowserContext]:
    """Anti-bot detection settings applied browser context.

    If use_session=True, tries to restore a saved session from:
      1. NOTE_SESSION env var (base64-encoded JSON, for CI)
      2. .auth/note_session.json file (for local dev)
    """
    browser = playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
    )

    storage_state = _load_session() if use_session else None

    kwargs = dict(
        viewport={"width": 1280, "height": 900},
        locale="ja-JP",
        user_agent=_USER_AGENT,
    )
    if storage_state:
        kwargs["storage_state"] = storage_state
        print("  セッションCookieを復元しました")

    context = browser.new_context(**kwargs)
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


def _load_session() -> dict | None:
    """Load session from NOTE_SESSION env var (base64) or file"""
    # Priority 1: env var (for CI)
    session_b64 = os.getenv("NOTE_SESSION")
    if session_b64:
        try:
            data = json.loads(base64.b64decode(session_b64))
            return data
        except Exception as e:
            print(f"  NOTE_SESSION環境変数のデコードに失敗: {e}")

    # Priority 2: local file
    if _SESSION_FILE.exists():
        try:
            data = json.loads(_SESSION_FILE.read_text())
            return data
        except Exception as e:
            print(f"  セッションファイルの読み込みに失敗: {e}")

    return None


def save_session(context: BrowserContext) -> None:
    """Save session state to file and print base64 for CI use"""
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(_SESSION_FILE))
    print(f"  セッションを保存しました: {_SESSION_FILE}")

    # Also print base64 for use as GitHub Secret
    data = _SESSION_FILE.read_bytes()
    b64 = base64.b64encode(data).decode()
    print(f"\n  === GitHub Secretsに設定してください ===")
    print(f"  Secret名: NOTE_SESSION")
    print(f"  値（以下の1行）:")
    print(f"  {b64}")
    print(f"  =====================================\n")


def _check_logged_in(page: Page) -> bool:
    """Check if the current page indicates a logged-in state"""
    url = page.url
    if "/login" in url:
        return False
    # Try accessing editor page to verify session is valid
    return True


def _diagnose_login_page(page: Page) -> None:
    """Log diagnostic info about the current login page state"""
    try:
        info = page.evaluate("""() => {
            const result = {};
            result.hasRecaptcha = !!document.querySelector('iframe[src*="recaptcha"]');
            result.hasCaptchaDiv = !!document.querySelector('[class*="captcha" i], [id*="captcha" i]');
            result.hasTurnstile = !!document.querySelector('iframe[src*="turnstile"]');
            const form = document.querySelector('form');
            result.hasForm = !!form;
            const errorEls = document.querySelectorAll('[class*="error" i], [class*="alert" i], [role="alert"]');
            result.errorTexts = Array.from(errorEls).map(e => e.textContent.trim()).filter(t => t.length > 0).slice(0, 3);
            result.url = location.href;
            return result;
        }""")
        print(f"  診断情報:")
        print(f"    URL: {info.get('url', '?')}")
        print(f"    reCAPTCHA: {info.get('hasRecaptcha')}, CAPTCHA div: {info.get('hasCaptchaDiv')}")
        if info.get('errorTexts'):
            print(f"    エラーメッセージ: {info['errorTexts']}")
    except Exception as e:
        print(f"  診断情報取得エラー: {e}")


def login(page: Page, email: str = None, password: str = None, max_retries: int = 2) -> bool:
    """Login to note.com.

    First tries cookie-based session restoration. If that fails and
    reCAPTCHA is present, returns False with instructions.

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

    # Step 1: Try cookie-based login (skip login page entirely)
    print("ログイン中...")
    session = _load_session()
    if session:
        print("  保存済みセッションでログインを試行...")
        # Navigate to a protected page to check if session is valid
        page.goto("https://note.com/notes/new", wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(2)

        current_url = page.url
        if "/login" not in current_url:
            print(f"  セッション復元成功: {current_url}")
            return True
        else:
            print("  保存済みセッションが無効です（期限切れの可能性）")

    # Step 2: Try form-based login (may fail with reCAPTCHA)
    LOGIN_URL = "https://note.com/login"

    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"\n  ログインリトライ ({attempt}/{max_retries})...")
            time.sleep(5 + attempt * 3)

        print("  フォームログインを試行中...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        time.sleep(2)

        # Check for reCAPTCHA before wasting time
        has_captcha = page.evaluate("""() => {
            return !!document.querySelector('iframe[src*="recaptcha"]')
                || !!document.querySelector('[class*="captcha" i], [id*="captcha" i]');
        }""")

        if has_captcha:
            print("  ⚠ reCAPTCHAが検出されました。自動ログインは不可能です。")
            print("  → ローカルで `python -m src.note_auth` を実行してセッションCookieを取得してください。")
            print("  → 取得したbase64値をGitHub Secretsの NOTE_SESSION に設定してください。")
            _diagnose_login_page(page)
            return False

        page.screenshot(path="debug_login_page.png")

        # Email input
        try:
            email_input = page.locator('input#email')
            email_input.wait_for(state="visible", timeout=10000)
            email_input.click()
            time.sleep(0.3)
            email_input.fill("")
            _human_type(page, 'input#email', email)
            print("  メールアドレス入力完了")
        except Exception as e:
            print(f"  メールアドレス入力エラー: {e}")
            continue

        time.sleep(0.5)

        # Password input
        try:
            password_input = page.locator('input#password')
            password_input.wait_for(state="visible", timeout=10000)
            password_input.click()
            time.sleep(0.3)
            password_input.fill("")
            _human_type(page, 'input#password', password)
            print("  パスワード入力完了")
        except Exception as e:
            print(f"  パスワード入力エラー: {e}")
            continue

        time.sleep(0.5)

        # Click login button
        try:
            login_button = page.locator('form button[type="submit"], form button:has-text("ログイン")')
            if login_button.count() == 0:
                login_button = page.locator('button:has-text("ログイン")')
            login_button.first.wait_for(state="visible", timeout=10000)
            login_button.first.click()
            print("  ログインボタンクリック完了")
        except Exception as e:
            print(f"  ログインボタンエラー: {e}")
            continue

        # Wait for URL to change
        try:
            page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=30000,
            )
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            print(f"  ログイン成功: {page.url}")
            return True
        except Exception:
            pass

        # Fallback URL check
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        current_url = page.url
        if "/login" not in current_url:
            print(f"  ログイン成功（フォールバック）: {current_url}")
            return True

        print(f"  ログイン失敗: {current_url}")
        _diagnose_login_page(page)

    print("  ログインリトライ上限に達しました")
    return False


def _human_type(page: Page, selector: str, text: str) -> None:
    """Type text with random delays to mimic human input"""
    element = page.locator(selector)
    element.click()
    time.sleep(0.3)
    for char in text:
        page.keyboard.type(char, delay=random.randint(30, 80))
    time.sleep(0.2)


def interactive_login():
    """Interactive login to export session cookies.

    Run this locally: python -m src.note_auth
    Then set the printed base64 value as NOTE_SESSION in GitHub Secrets.
    """
    email = os.getenv("NOTE_EMAIL")
    password = os.getenv("NOTE_PASSWORD")

    if not email or not password:
        print("NOTE_EMAIL と NOTE_PASSWORD を .env に設定してください")
        return

    print("=" * 50)
    print("note.com セッションCookieエクスポート")
    print("=" * 50)
    print()
    print("ブラウザが開きます。reCAPTCHAを手動で認証してください。")
    print()

    with sync_playwright() as p:
        browser, context = create_browser_context(p, headless=False, use_session=False)
        page = setup_page(context)

        LOGIN_URL = "https://note.com/login"
        page.goto(LOGIN_URL)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Fill email/password
        try:
            email_input = page.locator('input#email')
            email_input.wait_for(state="visible", timeout=10000)
            email_input.fill(email)

            password_input = page.locator('input#password')
            password_input.wait_for(state="visible", timeout=10000)
            password_input.fill(password)
            print("メールアドレスとパスワードを入力しました。")
        except Exception as e:
            print(f"入力エラー: {e}")

        print()
        print(">>> reCAPTCHAを認証して「ログイン」ボタンを押してください <<<")
        print(">>> ログイン完了後、自動的にCookieをエクスポートします <<<")
        print()

        # Wait for user to complete login (up to 5 minutes)
        try:
            page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=300000,  # 5 minutes
            )
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)
            print(f"ログイン成功！ URL: {page.url}")
            print()

            # Save session
            save_session(context)

        except Exception:
            print("タイムアウト: 5分以内にログインしてください。")

        browser.close()


if __name__ == "__main__":
    interactive_login()
