"""有料エリア設定画面のデバッグ用スクリプト"""

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time

load_dotenv()

def debug_paid_area():
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
        page.locator('textarea[placeholder="記事タイトル"]').fill("テスト記事")
        time.sleep(1)

        body = page.locator('.ProseMirror').first
        body.click()
        page.keyboard.type("これは無料部分です。\n\nここから有料にしたい部分です。\n\n詳しい解説はこちら。", delay=10)
        time.sleep(2)

        # 「公開に進む」ボタンをクリック
        print("「公開に進む」ボタンをクリック...")
        page.locator('button:has-text("公開に進む")').click()
        time.sleep(3)

        # 有料設定
        print("有料設定を選択...")
        page.locator('text="有料"').first.click()
        time.sleep(2)

        # 価格入力
        inputs = page.locator('input').all()
        for inp in inputs:
            value = inp.get_attribute("value")
            if value and value.isdigit() and int(value) >= 100:
                inp.click()
                inp.fill("")
                inp.fill("100")
                break
        time.sleep(1)

        # 「有料エリア設定」ボタンをクリック
        print("「有料エリア設定」ボタンをクリック...")
        page.locator('button:has-text("有料エリア設定")').click()
        time.sleep(3)

        page.screenshot(path="paid_area_screen.png")
        print("スクリーンショット保存: paid_area_screen.png")

        # ボタン一覧
        print("\n=== ボタン一覧 ===")
        buttons = page.locator('button').all()
        for i, btn in enumerate(buttons):
            text = btn.inner_text().strip()[:40]
            if text:
                print(f"{i}: '{text}'")

        # クリック可能な要素を探す
        print("\n=== クリック可能な要素 ===")
        clickables = page.locator('[role="button"], [class*="clickable"], [class*="select"]').all()
        for i, el in enumerate(clickables[:20]):
            text = el.inner_text().strip()[:30]
            if text:
                print(f"{i}: '{text}'")

        print("\n120秒間操作可能です。有料エリア選択画面を確認してください。")
        time.sleep(120)
        browser.close()

if __name__ == "__main__":
    debug_paid_area()
