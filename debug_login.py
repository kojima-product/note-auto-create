"""noteログインページのデバッグ用スクリプト"""

from playwright.sync_api import sync_playwright
import time

def debug_login_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="ja-JP",
        )
        page = context.new_page()

        print("ログインページにアクセス中...")
        page.goto("https://note.com/login")
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # スクリーンショットを保存
        page.screenshot(path="login_page.png")
        print("スクリーンショット保存: login_page.png")

        # ページ内のinput要素を調査
        print("\n=== input要素一覧 ===")
        inputs = page.query_selector_all("input")
        for i, inp in enumerate(inputs):
            attrs = page.evaluate("""(el) => {
                return {
                    type: el.type,
                    name: el.name,
                    id: el.id,
                    placeholder: el.placeholder,
                    className: el.className
                }
            }""", inp)
            print(f"{i}: {attrs}")

        # button要素を調査
        print("\n=== button要素一覧 ===")
        buttons = page.query_selector_all("button")
        for i, btn in enumerate(buttons):
            text = btn.inner_text()
            attrs = page.evaluate("""(el) => {
                return {
                    type: el.type,
                    className: el.className
                }
            }""", btn)
            print(f"{i}: text='{text}', {attrs}")

        print("\n10秒後に終了します...")
        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    debug_login_page()
