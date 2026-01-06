"""noteメンバーシップ・プラン限定公開のデバッグ用スクリプト"""

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time

load_dotenv()

def debug_membership_setting():
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
        page.keyboard.type("テスト本文です。", delay=10)
        time.sleep(2)

        # 「公開に進む」ボタンをクリック
        print("「公開に進む」ボタンをクリック...")
        page.locator('button:has-text("公開に進む")').click()
        time.sleep(3)

        page.screenshot(path="publish_page_initial.png")
        print("スクリーンショット保存: publish_page_initial.png")

        # ページをスクロールして全体を確認
        print("\nページを下にスクロール...")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        page.screenshot(path="publish_page_scrolled.png")
        print("スクリーンショット保存: publish_page_scrolled.png")
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

        # メンバーシップ関連のテキストを探す
        print("\n=== メンバーシップ関連のテキスト検索 ===")
        keywords = ["メンバーシップ", "プラン", "限定", "追加", "記事の追加", "マガジン", "サークル"]
        for keyword in keywords:
            elements = page.locator(f'text="{keyword}"').all()
            if elements:
                print(f"'{keyword}': {len(elements)}件")
                for i, elem in enumerate(elements):
                    try:
                        text = elem.inner_text()[:50]
                        print(f"  [{i}] {text}")
                    except:
                        pass

        # 「追加」ボタンを探す
        print("\n=== 「追加」ボタン検索 ===")
        add_buttons = page.locator('button:has-text("追加")').all()
        print(f"「追加」ボタン: {len(add_buttons)}個")
        for i, btn in enumerate(add_buttons):
            try:
                text = btn.inner_text().strip()
                box = btn.bounding_box()
                visible = btn.is_visible()
                print(f"  [{i}] text='{text}', visible={visible}, box={box}")
            except Exception as e:
                print(f"  [{i}] エラー: {e}")

        # 全てのセクションやコンテナを探す
        print("\n=== セクション/コンテナ構造 ===")
        sections_info = page.evaluate("""() => {
            const results = [];
            // セクションやコンテナを探す
            const containers = document.querySelectorAll('section, [class*="section"], [class*="Section"], [class*="container"], [class*="Container"], [class*="group"], [class*="Group"]');
            containers.forEach((el, idx) => {
                const text = el.textContent.trim().slice(0, 100);
                if (text) {
                    results.push({
                        index: idx,
                        tag: el.tagName,
                        className: el.className.slice(0, 80),
                        text: text
                    });
                }
            });
            return results;
        }""")

        for info in sections_info[:20]:  # 最初の20個
            print(f"  [{info['index']}] {info['tag']}: {info['className']}")
            print(f"      text: {info['text'][:60]}...")

        # 有料設定を選択
        print("\n\n=== 有料設定を選択 ===")
        try:
            paid_option = page.locator('text="有料"').first
            paid_option.click()
            time.sleep(2)
            print("有料オプションを選択しました")
            page.screenshot(path="publish_page_paid.png")
            print("スクリーンショット保存: publish_page_paid.png")
        except Exception as e:
            print(f"有料設定でエラー: {e}")

        # 再度メンバーシップ関連を探す（有料選択後）
        print("\n=== 有料選択後のメンバーシップ関連 ===")
        for keyword in ["メンバーシップ", "プラン", "限定公開", "追加"]:
            elements = page.locator(f'text="{keyword}"').all()
            if elements:
                print(f"'{keyword}': {len(elements)}件")

        # スクロールして全体を確認
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        page.screenshot(path="publish_page_paid_scrolled.png")
        print("スクリーンショット保存: publish_page_paid_scrolled.png")

        print("\n\n60秒間操作可能です。メンバーシップ・プラン限定公開の設定UIを手動で確認してください...")
        print("確認のポイント:")
        print("  1. 「記事の追加」という項目がどこにあるか")
        print("  2. 「メンバーシップ」の「プラン限定公開」のボタンや要素")
        print("  3. 追加ボタンの位置とテキスト")
        time.sleep(60)
        browser.close()

if __name__ == "__main__":
    debug_membership_setting()
