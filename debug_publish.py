"""note公開設定ページのデバッグ用スクリプト"""

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time

load_dotenv()

def debug_publish_page():
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

        # タイトルと本文を入力（公開に進むために必要）
        print("テスト用のタイトルと本文を入力...")
        page.locator('textarea[placeholder="記事タイトル"]').fill("テスト記事タイトル")
        time.sleep(1)

        body = page.locator('.ProseMirror').first
        body.click()
        page.keyboard.type("テスト本文です。", delay=10)
        time.sleep(2)

        # 「公開に進む」ボタンをクリック
        print("「公開に進む」ボタンをクリック...")
        page.locator('button:has-text("公開に進む")').click()
        time.sleep(3)

        page.screenshot(path="publish_page.png")
        print("スクリーンショット保存: publish_page.png")

        # input要素を探す
        print("\n=== input要素一覧 ===")
        inputs = page.query_selector_all("input")
        for i, inp in enumerate(inputs):
            inp_type = inp.get_attribute("type") or ""
            placeholder = inp.get_attribute("placeholder") or ""
            inp_id = inp.get_attribute("id") or ""
            inp_name = inp.get_attribute("name") or ""
            print(f"{i}: type='{inp_type}', placeholder='{placeholder}', id='{inp_id}', name='{inp_name}'")

        # ボタン一覧
        print("\n=== button要素一覧 ===")
        buttons = page.query_selector_all("button")
        for i, btn in enumerate(buttons):
            text = btn.inner_text().strip()[:40]
            if text:
                print(f"{i}: text='{text}'")

        # 設定関連のテキストを探す
        print("\n=== 設定関連のテキスト ===")
        keywords = ["有料", "価格", "販売", "タグ", "円", "無料", "ハッシュタグ"]
        for keyword in keywords:
            elements = page.locator(f'text="{keyword}"').all()
            if elements:
                print(f"'{keyword}': {len(elements)}件")

        # select要素を探す
        print("\n=== select要素一覧 ===")
        selects = page.query_selector_all("select")
        for i, sel in enumerate(selects):
            sel_id = sel.get_attribute("id") or ""
            sel_name = sel.get_attribute("name") or ""
            print(f"{i}: id='{sel_id}', name='{sel_name}'")

        print("\n60秒間操作可能です。有料設定やタグ設定のUIを確認してください...")
        print("確認後、ブラウザを閉じずにこのターミナルに戻って結果を教えてください。")
        time.sleep(60)
        browser.close()

if __name__ == "__main__":
    debug_publish_page()
