"""note公開設定フローのデバッグ用スクリプト"""

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time

load_dotenv()

def debug_publish_flow():
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
        page.locator('textarea[placeholder="記事タイトル"]').fill("テスト記事：有料設定テスト")
        time.sleep(1)

        body = page.locator('.ProseMirror').first
        body.click()
        page.keyboard.type("これはテスト本文です。\n\n有料部分のテストです。", delay=10)
        time.sleep(2)

        # 「公開に進む」ボタンをクリック
        print("「公開に進む」ボタンをクリック...")
        page.locator('button:has-text("公開に進む")').click()
        time.sleep(3)

        page.screenshot(path="publish_flow_1.png")
        print("スクリーンショット1保存")

        # タグを入力
        print("タグを入力...")
        tag_input = page.locator('input[placeholder="ハッシュタグを追加する"]')
        tag_input.fill("テスト")
        time.sleep(0.5)
        page.keyboard.press("Enter")
        time.sleep(1)

        page.screenshot(path="publish_flow_2.png")
        print("スクリーンショット2保存")

        # 有料設定
        print("有料設定を選択...")
        # 「有料」のテキストをクリック
        paid_option = page.locator('text="有料"').first
        paid_option.click()
        time.sleep(2)

        page.screenshot(path="publish_flow_3.png")
        print("スクリーンショット3保存")

        # 価格入力欄を探す
        print("\n=== 価格入力欄を探索 ===")
        inputs = page.locator('input').all()
        for i, inp in enumerate(inputs):
            inp_type = inp.get_attribute("type") or ""
            value = inp.get_attribute("value") or ""
            placeholder = inp.get_attribute("placeholder") or ""
            print(f"{i}: type='{inp_type}', value='{value}', placeholder='{placeholder}'")

        # 全てのボタンを確認
        print("\n=== ボタン一覧 ===")
        buttons = page.locator('button').all()
        for i, btn in enumerate(buttons):
            text = btn.inner_text().strip()[:30]
            if text:
                print(f"{i}: '{text}'")

        print("\n120秒間操作可能です。")
        print("公開設定画面で設定後、どのボタンを押せば下書き保存されるか確認してください。")
        time.sleep(120)
        browser.close()

if __name__ == "__main__":
    debug_publish_flow()
