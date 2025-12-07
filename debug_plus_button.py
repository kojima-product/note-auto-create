"""noteエディタの＋ボタンのデバッグ用スクリプト"""

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time

load_dotenv()

def debug_plus_button():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
        )
        page = context.new_page()

        # ログイン
        print("ログイン中...")
        page.goto("https://note.com/login")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        page.locator('input#email').fill(os.getenv("NOTE_EMAIL"))
        page.locator('input#password').fill(os.getenv("NOTE_PASSWORD"))
        page.locator('button:has-text("ログイン")').click()
        page.wait_for_url("**/", timeout=15000)
        time.sleep(2)
        print("ログイン成功")

        # 記事作成ページへ
        print("記事作成ページへ移動...")
        page.goto("https://note.com/notes/new")
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # タイトルと本文を入力
        print("テスト用のタイトルと本文を入力...")
        page.locator('textarea[placeholder="記事タイトル"]').fill("テスト記事タイトル")
        time.sleep(1)

        body = page.locator('.ProseMirror').first
        body.click()
        page.keyboard.type("これは無料部分のテスト本文です。", delay=10)
        page.keyboard.press("Enter")
        page.keyboard.press("Enter")
        time.sleep(1)

        # ＋ボタンを探してクリック
        print("\n＋ボタンを探しています...")

        # SVGやアイコンを含むボタンを探す
        plus_buttons = page.locator('button:has(svg), [role="button"]').all()
        print(f"ボタン候補: {len(plus_buttons)}個")

        # ツールバー周辺のボタンを探す
        page.screenshot(path="before_plus.png")

        # ProseMirrorエディタ内でEnterを押した後に表示される＋ボタンを探す
        # 一般的には空行にカーソルがあると＋ボタンが表示される
        plus_button = page.locator('[class*="plus"], [class*="add"], [aria-label*="追加"]').first

        if plus_button.is_visible():
            print("＋ボタンが見つかりました")
            plus_button.click()
            time.sleep(2)
        else:
            print("＋ボタンが見つかりません。手動でクリックしてください。")
            print("60秒間待機します...")
            time.sleep(10)

        page.screenshot(path="after_plus.png")
        print("スクリーンショット保存: after_plus.png")

        # ドロップダウンメニューの項目を探す
        print("\n=== メニュー項目を探索 ===")
        menu_items = page.locator('[role="menuitem"], [role="option"], li, [class*="menu"] button').all()
        for i, item in enumerate(menu_items[:20]):
            text = item.inner_text().strip()[:30]
            if text:
                print(f"{i}: '{text}'")

        # 有料関連のテキストを探す
        print("\n=== 有料関連のテキスト ===")
        paid_elements = page.locator('text=/有料|販売|ライン/').all()
        for i, el in enumerate(paid_elements):
            text = el.inner_text().strip()[:50]
            print(f"{i}: '{text}'")

        print("\n60秒間操作可能です。＋ボタンを押してメニューを確認してください...")
        time.sleep(60)
        browser.close()

if __name__ == "__main__":
    debug_plus_button()
