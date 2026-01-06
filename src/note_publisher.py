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
    DEFAULT_PRICE = 300  # デフォルト価格（円）
    PAID_LINE_MARKER = "===ここから有料==="

    def __init__(self, headless: bool = False, price: int = None, thumbnail_path: str = None):
        """
        Args:
            headless: ブラウザを非表示で実行するか（デバッグ時はFalse推奨）
            price: 有料記事の価格（円）
            thumbnail_path: サムネイル画像のパス（オプション）
        """
        self.headless = headless
        self.email = os.getenv("NOTE_EMAIL")
        self.password = os.getenv("NOTE_PASSWORD")
        self.price = price if price is not None else self.DEFAULT_PRICE
        self.thumbnail_path = thumbnail_path

        if not self.email or not self.password:
            raise ValueError("NOTE_EMAIL と NOTE_PASSWORD を .env に設定してください")

    def publish(self, article: Article, thumbnail_path: str = None) -> bool:
        """
        記事を投稿する

        Args:
            article: 投稿する記事
            thumbnail_path: サムネイル画像のパス（指定するとインスタンスの設定を上書き）

        Returns:
            成功した場合True
        """
        # サムネイルパスを決定（引数優先）
        effective_thumbnail = thumbnail_path or self.thumbnail_path
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
                if not self._create_and_publish(page, article, effective_thumbnail):
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

        # HTMLタグを削除
        content = re.sub(r'<[^>]+>', '', content)

        # マークダウンリンク [text](url) をテキストのみに変換
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

        # 取り消し線 ~~text~~ を通常テキストに変換
        content = re.sub(r'~~([^~]+)~~', r'\1', content)

        # テーブル形式を箇条書きに変換（もし残っていた場合）
        lines = content.split('\n')
        cleaned_lines = []
        in_code_block = False

        for line in lines:
            # コードブロックの開始/終了を検出
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                # コードブロックの言語指定を削除（```python → ```）
                cleaned_lines.append('```')
                continue

            if in_code_block:
                # コードブロック内はそのまま保持
                cleaned_lines.append(line)
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

            # * を - に変換（箇条書き）
            if re.match(r'^\s*\* ', line):
                line = re.sub(r'^(\s*)\* ', r'\1- ', line)

            cleaned_lines.append(line)

        content = '\n'.join(cleaned_lines)

        # 罫線（---）を削除（コードブロック外）
        content = re.sub(r'\n---+\n', '\n\n', content)

        # 連続する空行を1つに
        content = re.sub(r'\n{3,}', '\n\n', content)

        # # 見出しを ## に変換
        content = re.sub(r'^# ([^#])', r'## \1', content, flags=re.MULTILINE)

        # #### 以下の見出しを ### に変換
        content = re.sub(r'^####+ ', '### ', content, flags=re.MULTILINE)

        # 見出しの前に空行を確保
        content = re.sub(r'([^\n])\n(#{2,3} )', r'\1\n\n\2', content)

        # 箇条書きブロックの前に空行
        content = re.sub(r'([^\n-\n])\n(- )', r'\1\n\n\2', content)

        # 箇条書き項目間の余分な空行を削除
        content = re.sub(r'(^- .+)\n\n(?=- )', r'\1\n', content, flags=re.MULTILINE)

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

    def _create_and_publish(self, page: Page, article: Article, thumbnail_path: str = None) -> bool:
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

        # サムネイル画像をアップロード（記事編集画面で行う）
        # 注意: 失敗しても投稿は継続する
        if thumbnail_path:
            print(f"サムネイル画像をアップロード中: {thumbnail_path}")
            try:
                success = self._upload_thumbnail(page, thumbnail_path)
                if not success:
                    print("  サムネイルは手動で追加してください")
            except Exception as e:
                print(f"  サムネイルアップロードをスキップ: {e}")

        # ページを確実に安定させる
        time.sleep(2)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

        # 「公開に進む」ボタンをクリック
        print("公開設定画面へ移動中...")
        page.locator('button:has-text("公開に進む")').click()
        time.sleep(3)

        # タグを入力
        if article.tags:
            print(f"タグを入力中: {article.tags}")
            self._input_tags(page, article.tags)

        # 有料設定（価格が設定されている場合のみ）
        is_paid_article = self.price and self.price > 0
        if is_paid_article:
            print(f"有料設定中: {self.price}円")
            self._set_paid_article(page, self.price)

            # メンバーシップのプラン限定公開を設定
            self._set_membership_plan_restriction(page)
        else:
            print("無料記事として投稿します")

        # 投稿する
        print("投稿中...")

        if is_paid_article:
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
            for _ in range(5):
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

    def _set_membership_plan_restriction(self, page: Page) -> bool:
        """メンバーシップのプラン限定公開を設定"""
        try:
            print("メンバーシップのプラン限定公開を設定中...")
            time.sleep(1)

            # スクリーンショットを保存（デバッグ用）
            page.screenshot(path="debug_before_membership.png")

            # ページをスクロールして全体を読み込む
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.5)

            # 方法1: 「プラン限定公開」テキストを探してクリック
            plan_selectors = [
                'text="プラン限定公開"',
                'text="プラン限定"',
                ':text("プラン限定公開")',
            ]

            for selector in plan_selectors:
                try:
                    elem = page.locator(selector).first
                    if elem.is_visible(timeout=2000):
                        print(f"  「プラン限定公開」を発見: {selector}")
                        # 近くの追加ボタンを探す
                        # まずは要素をスクロールして表示
                        elem.scroll_into_view_if_needed()
                        time.sleep(0.3)

                        # 親要素内の「追加」ボタンを探す
                        parent_add_button = self._find_add_button_near_element(page, elem)
                        if parent_add_button:
                            parent_add_button.click()
                            print("  プラン限定公開の「追加」ボタンをクリック")
                            time.sleep(1)
                            page.screenshot(path="debug_after_membership.png")
                            return True
                except Exception:
                    continue

            # 方法2: メンバーシップセクションを探す
            membership_selectors = [
                'text="メンバーシップ"',
                ':text("メンバーシップ")',
                '[class*="membership"]',
                '[class*="Membership"]',
            ]

            for selector in membership_selectors:
                try:
                    elem = page.locator(selector).first
                    if elem.is_visible(timeout=2000):
                        print(f"  メンバーシップセクションを発見: {selector}")
                        elem.scroll_into_view_if_needed()
                        time.sleep(0.3)

                        # このセクション内の「追加」ボタンを探す
                        parent_add_button = self._find_add_button_near_element(page, elem)
                        if parent_add_button:
                            parent_add_button.click()
                            print("  メンバーシップの「追加」ボタンをクリック")
                            time.sleep(1)
                            page.screenshot(path="debug_after_membership.png")
                            return True
                except Exception:
                    continue

            # 方法3: JavaScriptで直接探す
            clicked = page.evaluate("""() => {
                // 「プラン限定公開」を含む要素を探す
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    const text = el.textContent || '';
                    if (text.includes('プラン限定公開') && el.children.length < 5) {
                        // 近くの「追加」ボタンを探す
                        let parent = el.parentElement;
                        for (let i = 0; i < 5 && parent; i++) {
                            const buttons = parent.querySelectorAll('button');
                            for (const btn of buttons) {
                                if (btn.textContent.trim() === '追加') {
                                    btn.click();
                                    return { success: true, method: 'plan_text' };
                                }
                            }
                            parent = parent.parentElement;
                        }
                    }
                }

                // 「メンバーシップ」セクション内の「追加」ボタンを探す
                for (const el of allElements) {
                    const text = el.textContent || '';
                    if (text.includes('メンバーシップ') && !text.includes('メンバーシップに') && el.children.length < 10) {
                        let parent = el.parentElement;
                        for (let i = 0; i < 5 && parent; i++) {
                            const buttons = parent.querySelectorAll('button');
                            for (const btn of buttons) {
                                if (btn.textContent.trim() === '追加') {
                                    btn.click();
                                    return { success: true, method: 'membership_section' };
                                }
                            }
                            parent = parent.parentElement;
                        }
                    }
                }

                return { success: false };
            }""")

            if clicked and clicked.get('success'):
                print(f"  JSで追加ボタンをクリック (method: {clicked.get('method')})")
                time.sleep(1)
                page.screenshot(path="debug_after_membership.png")
                return True

            print("  警告: プラン限定公開の設定が見つかりませんでした")
            page.screenshot(path="debug_membership_not_found.png")
            return False

        except Exception as e:
            print(f"  プラン限定公開設定でエラー: {e}")
            page.screenshot(path="error_membership_setting.png")
            return False

    def _find_add_button_near_element(self, page: Page, element) -> any:
        """指定された要素の近くにある「追加」ボタンを探す"""
        try:
            elem_box = element.bounding_box()
            if not elem_box:
                return None

            # 同じ行または近くにある「追加」ボタンを探す
            add_buttons = page.locator('button:has-text("追加")').all()

            for btn in add_buttons:
                try:
                    btn_box = btn.bounding_box()
                    if btn_box:
                        # Y座標が近い（同じ行付近）ボタンを探す
                        y_diff = abs(elem_box['y'] - btn_box['y'])
                        if y_diff < 50:  # 50px以内
                            return btn
                except Exception:
                    continue

            # フォールバック: 親要素を辿って「追加」ボタンを探す
            parent_info = page.evaluate("""(elemBox) => {
                const allButtons = document.querySelectorAll('button');
                for (const btn of allButtons) {
                    if (btn.textContent.trim() === '追加') {
                        const btnRect = btn.getBoundingClientRect();
                        const yDiff = Math.abs(elemBox.y - btnRect.y);
                        if (yDiff < 100) {
                            return {
                                found: true,
                                x: btnRect.x + btnRect.width / 2,
                                y: btnRect.y + btnRect.height / 2
                            };
                        }
                    }
                }
                return { found: false };
            }""", elem_box)

            if parent_info and parent_info.get('found'):
                # 座標でクリックするためのプロキシオブジェクトを返す
                class CoordButton:
                    def __init__(self, page, x, y):
                        self._page = page
                        self._x = x
                        self._y = y

                    def click(self):
                        self._page.mouse.click(self._x, self._y)

                return CoordButton(page, parent_info['x'], parent_info['y'])

        except Exception:
            pass

        return None

    def _upload_thumbnail(self, page: Page, thumbnail_path: str) -> bool:
        """サムネイル画像をアップロード（記事編集画面で実行）"""
        try:
            import os
            if not os.path.exists(thumbnail_path):
                print(f"  警告: サムネイル画像が見つかりません: {thumbnail_path}")
                return False

            # ページの一番上にスクロール
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)

            # モーダルが開いていたら閉じる（Escキーで閉じる）
            try:
                page.keyboard.press("Escape")
                time.sleep(0.5)
            except Exception:
                pass

            print("  見出し画像アイコンを探しています...")

            # 方法1: 見出し画像のコンテナやボタンを直接探す
            eyecatch_selectors = [
                # 見出し画像の追加ボタン（アイコン）
                '[data-testid="eyecatch-button"]',
                '[aria-label*="見出し"]',
                '[aria-label*="画像"]',
                'button[class*="eyecatch"]',
                'div[class*="eyecatch"] button',
                'div[class*="Eyecatch"] button',
                # SVGアイコンを含むボタン
                '.o-editorEyecatch button',
                '.o-editorEyecatch__button',
                # タイトル上部のエリア
                '[class*="header"] button:has(svg)',
                '[class*="Header"] button:has(svg)',
            ]

            icon_clicked = False
            for selector in eyecatch_selectors:
                try:
                    elem = page.locator(selector)
                    if elem.count() > 0 and elem.first.is_visible(timeout=1000):
                        print(f"  見出し画像ボタンを発見: {selector}")
                        elem.first.click()
                        icon_clicked = True
                        time.sleep(1)
                        break
                except Exception:
                    continue

            # 方法2: タイトル入力欄の位置を基準に、その上にある要素を探してクリック
            if not icon_clicked:
                print("  セレクターで見つからないため、位置ベースで探索...")
                title_area = page.locator('textarea[placeholder="記事タイトル"]')
                if title_area.count() > 0:
                    title_box = title_area.bounding_box()
                    if title_box:
                        # タイトルの上にある全てのクリック可能な要素を探す
                        # JavaScriptを使って要素を取得
                        elements_info = page.evaluate("""() => {
                            const title = document.querySelector('textarea[placeholder="記事タイトル"]');
                            if (!title) return null;
                            const titleRect = title.getBoundingClientRect();

                            // タイトルより上にある全ての要素
                            const allElements = document.querySelectorAll('button, [role="button"], div[class*="eyecatch"], div[class*="Eyecatch"], svg');
                            const results = [];

                            allElements.forEach((el, idx) => {
                                const rect = el.getBoundingClientRect();
                                // タイトルより上にある要素
                                if (rect.bottom < titleRect.top && rect.top > 0) {
                                    results.push({
                                        index: idx,
                                        tag: el.tagName,
                                        className: el.className,
                                        x: rect.x + rect.width/2,
                                        y: rect.y + rect.height/2,
                                        width: rect.width,
                                        height: rect.height
                                    });
                                }
                            });
                            return results;
                        }""")

                        if elements_info:
                            print(f"  タイトル上部に{len(elements_info)}個の要素を発見")
                            for el in elements_info:
                                print(f"    - {el['tag']}: {el['className'][:50] if el['className'] else 'no class'} at ({el['x']:.0f}, {el['y']:.0f})")

                            # 見出し画像っぽい要素（eyecatch, Eyecatch, header, Header を含む）を優先
                            for el in elements_info:
                                class_name = el.get('className', '') or ''
                                if any(keyword in class_name.lower() for keyword in ['eyecatch', 'header', 'image', 'thumbnail']):
                                    print(f"  見出し画像要素をクリック: ({el['x']:.0f}, {el['y']:.0f})")
                                    page.mouse.click(el['x'], el['y'])
                                    icon_clicked = True
                                    time.sleep(1)
                                    break

                            # まだクリックできていなければ、タイトル上部の中央あたりをクリック
                            if not icon_clicked and elements_info:
                                # 中央付近の要素を探す
                                center_x = title_box['x'] + title_box['width'] / 2
                                closest_el = None
                                min_dist = float('inf')
                                for el in elements_info:
                                    dist = abs(el['x'] - center_x)
                                    if dist < min_dist:
                                        min_dist = dist
                                        closest_el = el
                                if closest_el:
                                    print(f"  中央付近の要素をクリック: ({closest_el['x']:.0f}, {closest_el['y']:.0f})")
                                    page.mouse.click(closest_el['x'], closest_el['y'])
                                    icon_clicked = True
                                    time.sleep(1)

            # 方法3: フォールバック - 直接座標でクリック
            if not icon_clicked:
                print("  フォールバック: タイトル上部の座標をクリック")
                title_area = page.locator('textarea[placeholder="記事タイトル"]')
                if title_area.count() > 0:
                    title_box = title_area.bounding_box()
                    if title_box:
                        # 異なる位置を順番にクリック
                        positions = [
                            (title_box['x'] + title_box['width'] / 2, title_box['y'] - 50),
                            (title_box['x'] + title_box['width'] / 2, title_box['y'] - 80),
                            (title_box['x'] + title_box['width'] / 2, title_box['y'] - 100),
                        ]
                        for x, y in positions:
                            print(f"  位置をクリック: ({x:.0f}, {y:.0f})")
                            page.mouse.click(x, y)
                            time.sleep(0.8)
                            # メニューが表示されたかチェック
                            upload_menu = page.locator('text="画像をアップロード"')
                            if upload_menu.count() > 0 and upload_menu.first.is_visible():
                                icon_clicked = True
                                break

            # スクリーンショット保存（デバッグ用）
            page.screenshot(path="debug_thumbnail_menu.png")

            # Step 2: 「画像をアップロード」メニューをクリック
            upload_menu = page.locator('text="画像をアップロード"')
            if upload_menu.count() > 0 and upload_menu.first.is_visible():
                print("  「画像をアップロード」メニューを発見")

                # ファイル選択ダイアログを待機しながらクリック
                with page.expect_file_chooser(timeout=10000) as fc_info:
                    upload_menu.first.click()

                file_chooser = fc_info.value
                file_chooser.set_files(thumbnail_path)
                print(f"  ファイルを選択: {thumbnail_path}")
                time.sleep(2)

                # Step 3: 画角調整画面（CropModal）で「保存」ボタンをクリック
                page.screenshot(path="debug_thumbnail_crop.png")

                # CropModalが表示されるのを待つ
                time.sleep(1)

                # CropModal内の保存ボタンを探す（複数の方法で試行）
                save_clicked = False

                # 方法1: JavaScriptで直接クリック（最も確実）
                try:
                    print("  JSでモーダル内の保存ボタンをクリック...")
                    clicked = page.evaluate("""() => {
                        // ReactModalPortal内のボタンを探す
                        const portals = document.querySelectorAll('.ReactModalPortal');
                        for (const portal of portals) {
                            const buttons = portal.querySelectorAll('button');
                            // 「保存」ボタンを探す（「リマインダー」「キャンセル」「保存」の順）
                            for (const btn of buttons) {
                                const text = btn.textContent.trim();
                                if (text === '保存') {
                                    btn.click();
                                    return { clicked: true, text: text };
                                }
                            }
                        }
                        // フォールバック: 全ページで「保存」を含むボタン
                        const allButtons = document.querySelectorAll('button');
                        for (const btn of allButtons) {
                            const text = btn.textContent.trim();
                            if (text === '保存') {
                                btn.click();
                                return { clicked: true, text: text };
                            }
                        }
                        return { clicked: false };
                    }""")
                    if clicked and clicked.get('clicked'):
                        print(f"  「{clicked.get('text', '保存')}」ボタンをクリックしました")
                        save_clicked = True
                        time.sleep(2)
                        print("  サムネイル画像をアップロードしました！")
                        return True
                except Exception as e:
                    print(f"  JSクリックエラー: {e}")

                # 方法2: dispatchEventでクリックイベントを発火
                if not save_clicked:
                    try:
                        print("  dispatchEventで保存ボタンをクリック...")
                        clicked = page.evaluate("""() => {
                            const portals = document.querySelectorAll('.ReactModalPortal');
                            for (const portal of portals) {
                                const buttons = portal.querySelectorAll('button');
                                for (const btn of buttons) {
                                    if (btn.textContent.trim() === '保存') {
                                        // 複数のイベントを発火
                                        btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                        btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                                        btn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                        return true;
                                    }
                                }
                            }
                            return false;
                        }""")
                        if clicked:
                            save_clicked = True
                            time.sleep(2)
                            print("  サムネイル画像をアップロードしました！")
                            return True
                    except Exception as e:
                        print(f"  dispatchEventエラー: {e}")

                # 方法3: Playwrightのforce clickでモーダル内ボタンをクリック
                if not save_clicked:
                    modal_save_selectors = [
                        '.ReactModalPortal button:text-is("保存")',
                        '.ReactModal__Content button:text-is("保存")',
                        'button:text-is("保存")',
                    ]

                    for selector in modal_save_selectors:
                        try:
                            save_btn = page.locator(selector)
                            if save_btn.count() > 0:
                                print(f"  保存ボタンを発見: {selector}")
                                save_btn.first.click(force=True, timeout=5000)
                                save_clicked = True
                                time.sleep(2)
                                print("  サムネイル画像をアップロードしました！")
                                return True
                        except Exception as e:
                            print(f"  セレクター {selector} でエラー: {e}")
                            continue

                print("  警告: 保存ボタンのクリックに失敗しました")
                # モーダルを閉じて続行できるようにする
                self._close_modal(page)
                return False
            else:
                print("  警告: 「画像をアップロード」メニューが見つかりません")
                print("  ヒント: note.comのUIが変更された可能性があります。手動でサムネイルを追加してください。")
                page.screenshot(path="debug_thumbnail_no_menu.png")
                return False

        except Exception as e:
            print(f"  サムネイルアップロードエラー: {e}")
            page.screenshot(path="error_thumbnail_upload.png")
            # モーダルを閉じて続行できるようにする
            self._close_modal(page)
            return False

    def _close_modal(self, page: Page) -> None:
        """開いているモーダルを閉じる"""
        try:
            # Escキーで閉じる
            page.keyboard.press("Escape")
            time.sleep(0.5)

            # モーダルの×ボタンを探してクリック
            close_buttons = [
                '[class*="Modal"] button[aria-label="Close"]',
                '[class*="Modal"] button[aria-label="閉じる"]',
                '.ReactModal__Content button:first-child',
            ]
            for selector in close_buttons:
                try:
                    btn = page.locator(selector)
                    if btn.count() > 0 and btn.first.is_visible():
                        btn.first.click(force=True)
                        time.sleep(0.5)
                        break
                except Exception:
                    continue

            # もう一度Escキー
            page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass

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
