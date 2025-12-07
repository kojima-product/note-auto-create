"""noteエディタページのデバッグ用スクリプト"""

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time

load_dotenv()

def debug_editor_page():
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

        page.screenshot(path="editor_page.png")
        print("スクリーンショット保存: editor_page.png")

        # タイトル入力欄を探す
        print("\n=== textarea要素一覧 ===")
        textareas = page.query_selector_all("textarea")
        for i, ta in enumerate(textareas):
            attrs = page.evaluate("""(el) => {
                return {
                    placeholder: el.placeholder,
                    className: el.className,
                    id: el.id
                }
            }""", ta)
            print(f"{i}: {attrs}")

        # 本文エリアを探す
        print("\n=== contenteditable要素 ===")
        editables = page.query_selector_all('[contenteditable="true"]')
        for i, el in enumerate(editables):
            attrs = page.evaluate("""(el) => {
                return {
                    className: el.className,
                    tagName: el.tagName
                }
            }""", el)
            print(f"{i}: {attrs}")

        # ボタン一覧
        print("\n=== button要素一覧 ===")
        buttons = page.query_selector_all("button")
        for i, btn in enumerate(buttons):
            text = btn.inner_text().strip()[:30]
            if text:
                class_name = btn.get_attribute("class") or ""
                print(f"{i}: text='{text}', class='{class_name[:50]}'")

        # 公開設定や有料設定のリンク/ボタンを探す
        print("\n=== 設定関連のテキストを含む要素 ===")
        keywords = ["有料", "価格", "販売", "タグ", "公開", "設定", "下書き"]
        for keyword in keywords:
            elements = page.query_selector_all(f'text="{keyword}"')
            if elements:
                print(f"'{keyword}': {len(elements)}件見つかりました")

        print("\n30秒間操作可能です。有料設定やタグ設定のUIを確認してください...")
        time.sleep(30)
        browser.close()

if __name__ == "__main__":
    debug_editor_page()
