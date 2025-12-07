"""note投稿モジュール - Playwrightを使用してnoteに投稿"""

import os
import time
from playwright.sync_api import sync_playwright, Page
from dotenv import load_dotenv
from .article_generator import Article

load_dotenv()


class NotePublisher:
    """noteに記事を投稿するクラス"""

    LOGIN_URL = "https://note.com/login"
    NEW_TEXT_URL = "https://note.com/notes/new"
    DEFAULT_PRICE = 100  # デフォルト価格（円）
    PAID_LINE_MARKER = "===ここから有料==="

    def __init__(self, headless: bool = False, price: int = None):
        """
        Args:
            headless: ブラウザを非表示で実行するか（デバッグ時はFalse推奨）
            price: 有料記事の価格（円）
        """
        self.headless = headless
        self.email = os.getenv("NOTE_EMAIL")
        self.password = os.getenv("NOTE_PASSWORD")
        self.price = price if price is not None else self.DEFAULT_PRICE

        if not self.email or not self.password:
            raise ValueError("NOTE_EMAIL と NOTE_PASSWORD を .env に設定してください")

    def publish(self, article: Article) -> bool:
        """
        記事を投稿する

        Args:
            article: 投稿する記事

        Returns:
            成功した場合True
        """
        with sync_playwright() as p:
            # headlessモードでもボット検出を回避するための設定
            browser = p.chromium.launch(
                headless=self.headless,
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
            page = context.new_page()

            # webdriverプロパティを削除してボット検出を回避
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            try:
                # ログイン
                if not self._login(page):
                    print("ログインに失敗しました")
                    return False

                print("ログイン成功")

                # 記事作成・投稿
                if not self._create_and_publish(page, article):
                    print("投稿に失敗しました")
                    return False

                print("投稿成功！")
                return True

            except Exception as e:
                print(f"エラーが発生しました: {e}")
                page.screenshot(path="error_screenshot.png")
                return False

            finally:
                browser.close()

    # 後方互換性のため
    def publish_draft(self, article: Article) -> bool:
        return self.publish(article)

    def _login(self, page: Page) -> bool:
        """noteにログイン"""
        print("ログイン中...")

        page.goto(self.LOGIN_URL)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # デバッグ用スクリーンショット
        page.screenshot(path="debug_login_page.png")
        print("  デバッグ: ログインページのスクリーンショットを保存")

        # メールアドレス入力
        try:
            email_input = page.locator('input#email')
            email_input.wait_for(state="visible", timeout=10000)
            email_input.fill(self.email)
            print("  メールアドレス入力完了")
        except Exception as e:
            print(f"  メールアドレス入力エラー: {e}")
            page.screenshot(path="debug_email_error.png")
            return False

        # パスワード入力
        try:
            password_input = page.locator('input#password')
            password_input.wait_for(state="visible", timeout=10000)
            password_input.fill(self.password)
            print("  パスワード入力完了")
        except Exception as e:
            print(f"  パスワード入力エラー: {e}")
            page.screenshot(path="debug_password_error.png")
            return False

        # ログインボタンクリック
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
            # ログイン後のページ遷移を待つ
            page.wait_for_url("**/", timeout=30000)
            time.sleep(3)
            page.screenshot(path="debug_after_login.png")
            print("  ログイン後のスクリーンショットを保存")
            return True
        except Exception as e:
            print(f"  ログイン後の画面遷移エラー: {e}")
            page.screenshot(path="debug_login_failed.png")
            return False

    def _clean_content_for_note(self, content: str) -> str:
        """note.com向けにコンテンツを整形"""
        import re

        # テーブル形式を箇条書きに変換（もし残っていた場合）
        lines = content.split('\n')
        cleaned_lines = []
        in_code_block = False
        code_block_content = []

        for line in lines:
            # コードブロックの開始/終了を検出
            if line.strip().startswith('```'):
                if not in_code_block:
                    # コードブロック開始
                    in_code_block = True
                    code_block_content = []
                    # 言語指定を除去（```python → ```）
                    cleaned_lines.append('```')
                else:
                    # コードブロック終了
                    in_code_block = False
                    # コード内容を追加
                    for code_line in code_block_content:
                        cleaned_lines.append(code_line)
                    cleaned_lines.append('```')
                continue

            if in_code_block:
                # コードブロック内はそのまま保持
                code_block_content.append(line)
                continue

            # テーブルヘッダー区切り行をスキップ
            if re.match(r'^\|[\s\-:]+\|', line):
                continue
            # テーブル行を箇条書きに変換
            if line.startswith('|') and line.endswith('|'):
                cells = [c.strip() for c in line.strip('|').split('|')]
                if cells and cells[0]:
                    cleaned_lines.append(f"- {': '.join(cells)}")
                continue

            cleaned_lines.append(line)

        content = '\n'.join(cleaned_lines)

        # 罫線（---）を削除（コードブロック外）
        content = re.sub(r'\n---+\n', '\n\n', content)

        # 連続する空行を1つに
        content = re.sub(r'\n{3,}', '\n\n', content)

        # # 見出しを ## に変換
        content = re.sub(r'^# ([^#])', r'## \1', content, flags=re.MULTILINE)

        # 見出しの前に空行を確保
        content = re.sub(r'([^\n])\n(#{2,3} )', r'\1\n\n\2', content)

        # 箇条書きブロックの前に空行
        content = re.sub(r'([^\n-\n])\n(- )', r'\1\n\n\2', content)

        # 箇条書き項目間の余分な空行を削除
        content = re.sub(r'(^- .+)\n\n(?=- )', r'\1\n', content, flags=re.MULTILINE)

        # コードブロックの前後に空行を確保
        content = re.sub(r'([^\n])\n```', r'\1\n\n```', content)
        content = re.sub(r'```\n([^\n`])', r'```\n\n\1', content)

        # 先頭と末尾の空白を削除
        content = content.strip()

        # 最終チェック：連続空行を1つに
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content

    def _type_content(self, page: Page, content: str, delay: int = 2) -> None:
        """コンテンツをタイピングアニメーションで入力（マークダウン対応）"""
        # note.com向けに整形
        content = self._clean_content_for_note(content)
        # ストリーミング形式でタイピング（マークダウンが正しくレンダリングされる）
        page.keyboard.type(content, delay=delay)
        time.sleep(1)

    def _create_and_publish(self, page: Page, article: Article) -> bool:
        """記事を作成して投稿"""
        print("記事作成ページへ移動中...")

        page.goto(self.NEW_TEXT_URL)
        page.wait_for_load_state("networkidle")
        time.sleep(5)  # ページ読み込みを待つ（headlessモードではより長く）

        # DOMの完全読み込みを待つ
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        # デバッグ用スクリーンショット
        page.screenshot(path="debug_new_article_page.png")
        print("  デバッグ: 記事作成ページのスクリーンショットを保存")

        # ページURLを確認（リダイレクトされていないか）
        current_url = page.url
        print(f"  現在のURL: {current_url}")
        if "login" in current_url.lower():
            print("  警告: ログインページにリダイレクトされました。再ログインが必要かもしれません。")
            page.screenshot(path="debug_redirected_to_login.png")
            return False

        # タイトル入力（複数のセレクターを試す）
        print("タイトルを入力中...")
        title_selectors = [
            'textarea[placeholder="記事タイトル"]',
            'textarea[placeholder*="タイトル"]',
            'textarea.title',
            '[data-testid="title-input"]',
            'textarea:first-of-type',
        ]

        title_input = None
        for selector in title_selectors:
            try:
                locator = page.locator(selector)
                if locator.count() > 0:
                    # 要素が見つかった場合、表示されるまで待つ
                    locator.first.wait_for(state="visible", timeout=10000)
                    title_input = locator.first
                    print(f"  タイトル入力欄を発見: {selector}")
                    break
            except Exception:
                continue

        if not title_input:
            # 最後の手段: ページ上の最初のtextareaを使用
            print("  警告: 標準セレクターでタイトル入力欄が見つかりません。textareaを検索中...")
            page.screenshot(path="debug_title_not_found.png")
            try:
                all_textareas = page.locator('textarea').all()
                print(f"  ページ上のtextarea数: {len(all_textareas)}")
                if all_textareas:
                    title_input = all_textareas[0]
            except Exception as e:
                print(f"  textarea検索エラー: {e}")

        if not title_input:
            print("エラー: タイトル入力欄が見つかりません")
            return False

        title_input.fill(article.title)
        time.sleep(1)

        # 本文入力（マーカー含む全体をタイピング）
        content = article.content

        # Whisk用サムネイルプロンプトを記事末尾に追加
        if article.thumbnail_prompt:
            content = content.rstrip()
            content += "\n\n## Thumbnail Prompt (for Whisk)\n"
            content += f"{article.thumbnail_prompt}"

        print("本文を入力中...")
        body_area = page.locator('.ProseMirror').first
        body_area.click()
        time.sleep(0.5)

        # 全文をタイピングアニメーションで入力
        print(f"  記事を入力中... ({len(content)}文字)")
        self._type_content(page, content)
        time.sleep(2)

        # 「公開に進む」ボタンをクリック
        print("公開設定画面へ移動中...")
        page.locator('button:has-text("公開に進む")').click()
        time.sleep(3)

        # タグを入力
        if article.tags:
            print(f"タグを入力中: {article.tags}")
            self._input_tags(page, article.tags)

        # 有料設定（価格）
        if self.price and self.price > 0:
            print(f"有料設定中: {self.price}円")
            self._set_paid_article(page, self.price)

        # 投稿する
        print("投稿中...")

        # 有料の場合は「有料エリア設定」ボタン → 有料ライン選択画面 → 投稿
        paid_publish_button = page.locator('button:has-text("有料エリア設定")')
        if paid_publish_button.is_visible():
            paid_publish_button.click()
            time.sleep(3)

            # 有料ライン選択画面が表示される
            # 「===ここから有料===」マーカーの位置を探して、その直前のラインを設定
            self._select_paid_line_position(page)

            # 「投稿する」ボタンをクリック
            final_publish = page.locator('button:has-text("投稿する")')
            if final_publish.is_visible():
                final_publish.click()
                time.sleep(5)
                return True

        # 無料の場合は直接「投稿する」ボタン
        publish_button = page.locator('button:has-text("投稿する")')
        if publish_button.is_visible():
            publish_button.click()
            time.sleep(5)
            return True

        return False

    def _select_paid_line_position(self, page: Page) -> None:
        """有料ライン選択画面で、マーカーの位置に有料ラインを設定"""
        try:
            time.sleep(2)  # 画面が完全に読み込まれるのを待つ

            # スクロール可能な領域を探してスクロールする
            # マーカーを探すために上から下にスクロール
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.5)

            # デバッグ用スクリーンショット
            page.screenshot(path="debug_paid_line_selection.png")
            print("  デバッグ: 有料ライン選択画面のスクリーンショットを保存")

            # 「ラインをこの場所に変更」または類似のボタンを探す
            # noteの有料ライン選択画面のボタンテキストを複数パターンで検索
            button_patterns = [
                'button:has-text("ラインをこの場所に変更")',
                'button:has-text("この場所に変更")',
                'button:has-text("ここに設定")',
                '[class*="line"] button',
            ]

            line_buttons = []
            for pattern in button_patterns:
                buttons = page.locator(pattern).all()
                if buttons:
                    line_buttons = buttons
                    print(f"  ボタン発見: {pattern} ({len(buttons)}個)")
                    break

            if not line_buttons:
                print("  有料ライン選択ボタンが見つかりません")
                # ページのHTMLを取得してデバッグ
                return

            print(f"  有料ライン選択ボタン: {len(line_buttons)}個発見")

            # マーカーテキストを探す（複数パターン）
            marker_patterns = [
                self.PAID_LINE_MARKER,  # ===ここから有料===
                "ここから有料",
                "有料エリア",
            ]

            marker_element = None
            # スクロールしながらマーカーを探す
            for scroll_attempt in range(5):
                for pattern in marker_patterns:
                    try:
                        elem = page.locator(f'text="{pattern}"').first
                        if elem.is_visible(timeout=500):
                            # マーカーを画面中央にスクロール
                            elem.scroll_into_view_if_needed()
                            time.sleep(0.3)
                            marker_element = elem
                            print(f"  マーカー発見: {pattern}")
                            break
                    except:
                        continue
                if marker_element:
                    break
                # 下にスクロールして再検索
                page.evaluate("window.scrollBy(0, 300)")
                time.sleep(0.3)

            if marker_element:
                # マーカーが見つかった場合、その直前のボタンをクリック
                marker_box = marker_element.bounding_box()
                if marker_box:
                    marker_y = marker_box['y']
                    print(f"  マーカー位置: Y={marker_y}")

                    # マーカーより上にある最も近いボタンを探す
                    closest_button = None
                    closest_distance = float('inf')

                    for i, btn in enumerate(line_buttons):
                        btn_box = btn.bounding_box()
                        if btn_box:
                            btn_y = btn_box['y']
                            print(f"    ボタン{i}: Y={btn_y}")
                            # マーカーより上にあるボタン
                            if btn_y < marker_y:
                                distance = marker_y - btn_y
                                if distance < closest_distance:
                                    closest_distance = distance
                                    closest_button = btn

                    if closest_button:
                        print(f"  マーカー直前のボタンをクリック (距離: {closest_distance})")
                        closest_button.click()
                        time.sleep(1)
                        return

            # マーカーが見つからない場合、最初のボタンをクリック
            if len(line_buttons) >= 1:
                print("  マーカーが見つからないため、最初のボタンを使用")
                line_buttons[0].click()
                time.sleep(1)

        except Exception as e:
            print(f"  有料ライン位置設定でエラー: {e}")
            page.screenshot(path="error_paid_line_selection.png")

    def _input_tags(self, page: Page, tags: list[str]) -> None:
        """ハッシュタグを入力"""
        tag_input = page.locator('input[placeholder="ハッシュタグを追加する"]')

        for tag in tags:
            tag_input.click()
            tag_input.fill(tag)
            time.sleep(0.3)
            page.keyboard.press("Enter")
            time.sleep(0.5)

    def _set_paid_article(self, page: Page, price: int) -> None:
        """有料記事の価格設定"""
        # 「有料」オプションをクリック
        paid_label = page.locator('text="有料"').first
        paid_label.click()
        time.sleep(2)

        # 価格入力欄を探して入力
        try:
            # 価格入力欄（デフォルト500が入っている）
            inputs = page.locator('input').all()
            for inp in inputs:
                value = inp.get_attribute("value")
                if value and value.isdigit() and int(value) >= 100:
                    inp.click()
                    inp.fill("")
                    inp.fill(str(price))
                    print(f"  価格を{price}円に設定")
                    break
        except Exception as e:
            print(f"価格設定でエラー: {e}")

        time.sleep(1)

    def test_login(self) -> bool:
        """ログインのみをテスト"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="ja-JP",
            )
            page = context.new_page()

            try:
                result = self._login(page)
                if result:
                    print("ログインテスト成功！")
                    time.sleep(3)
                return result
            finally:
                browser.close()


if __name__ == "__main__":
    publisher = NotePublisher(headless=False)
    publisher.test_login()
