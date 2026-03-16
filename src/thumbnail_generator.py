"""サムネイル画像生成モジュール - Gemini API (Nano Banana Pro)を使用"""

import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()


class ThumbnailGenerator:
    """Gemini API (Nano Banana Pro)を使用してサムネイル画像を生成するクラス"""

    # noteのサムネイル推奨サイズ
    NOTE_THUMBNAIL_WIDTH = 1280
    NOTE_THUMBNAIL_HEIGHT = 670

    MODELS = {
        "flash": "gemini-2.0-flash-exp",  # Nano Banana (高速・画像生成対応)
        "pro": "gemini-3-pro-image-preview",  # Nano Banana Pro (高品質)
    }

    def __init__(self, model: str = "pro"):
        """
        Args:
            model: 使用するモデル ("flash" または "pro")
        """
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY を .env に設定してください")

        self.model = self.MODELS.get(model, self.MODELS["pro"])
        print(f"サムネイル生成モデル: {self.model}")

    def generate(self, prompt: str, output_path: str = None) -> Optional[str]:
        """
        プロンプトからサムネイル画像を生成

        Args:
            prompt: 画像生成用プロンプト（英語推奨）
            output_path: 出力ファイルパス（指定しない場合は自動生成）

        Returns:
            生成された画像のファイルパス、失敗時はNone
        """
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            print("エラー: google-genai パッケージがインストールされていません")
            print("  pip install google-genai pillow")
            return None

        # 出力パスの設定
        if output_path is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path(__file__).parent.parent / "output" / "thumbnails"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"thumbnail_{timestamp}.png")

        try:
            # Gemini クライアントの初期化
            client = genai.Client(api_key=self.api_key)

            # サムネイル用のプロンプトを最適化
            optimized_prompt = self._optimize_prompt(prompt)
            print(f"サムネイル生成中...")
            print(f"  プロンプト: {optimized_prompt[:100]}...")

            # 画像生成
            response = client.models.generate_content(
                model=self.model,
                contents=[optimized_prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]
                )
            )

            # レスポンスから画像を抽出
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    # 画像データを保存
                    image_data = part.inline_data.data
                    mime_type = part.inline_data.mime_type

                    # MIMEタイプに応じて拡張子を決定
                    ext = ".png"
                    if "jpeg" in mime_type or "jpg" in mime_type:
                        ext = ".jpg"
                    elif "webp" in mime_type:
                        ext = ".webp"

                    # 拡張子を更新
                    if not output_path.endswith(ext):
                        output_path = output_path.rsplit(".", 1)[0] + ext

                    # ファイルに保存
                    import base64
                    if isinstance(image_data, str):
                        image_bytes = base64.b64decode(image_data)
                    else:
                        image_bytes = image_data

                    with open(output_path, "wb") as f:
                        f.write(image_bytes)

                    # noteの推奨サイズにリサイズ
                    output_path = self._resize_to_note_size(output_path)
                    print(f"  サムネイル生成完了: {output_path}")
                    return output_path

            print("  警告: 画像が生成されませんでした")
            return None

        except Exception as e:
            print(f"サムネイル生成エラー: {e}")
            return None

    def _resize_to_note_size(self, image_path: str) -> str:
        """画像をnoteの推奨サムネイルサイズにリサイズ"""
        try:
            from PIL import Image

            with Image.open(image_path) as img:
                original_size = f"{img.width}x{img.height}"

                # noteの推奨サイズにリサイズ
                target_size = (self.NOTE_THUMBNAIL_WIDTH, self.NOTE_THUMBNAIL_HEIGHT)
                resized = img.resize(target_size, Image.Resampling.LANCZOS)

                # 同じパスに保存（上書き）
                # JPEGの場合は品質を指定
                if image_path.lower().endswith(('.jpg', '.jpeg')):
                    resized.save(image_path, quality=95)
                else:
                    resized.save(image_path)

                print(f"  リサイズ完了: {original_size} → {self.NOTE_THUMBNAIL_WIDTH}x{self.NOTE_THUMBNAIL_HEIGHT}")

            return image_path

        except Exception as e:
            print(f"  リサイズエラー（元画像を使用）: {e}")
            return image_path

    def _optimize_prompt(self, prompt: str) -> str:
        """サムネイル用にプロンプトを最適化"""
        # noteのサムネイルサイズを指定
        size_spec = f"Image size: {self.NOTE_THUMBNAIL_WIDTH}x{self.NOTE_THUMBNAIL_HEIGHT}px, aspect ratio 1.91:1."

        # プロンプトが短い場合はスタイルヒントを追加
        if len(prompt) < 100:
            optimized = f"{prompt}. {size_spec} Modern tech blog thumbnail, vibrant colors, no text in image."
        else:
            optimized = f"{prompt}. {size_spec}"

        return optimized

    def generate_from_article(self, title: str, tags: List[str] = None, use_japanese: bool = True) -> Optional[str]:
        """
        記事のタイトルとタグからサムネイルを自動生成

        Args:
            title: 記事タイトル
            tags: タグリスト
            use_japanese: Trueの場合、日本語タイトルをそのまま使用

        Returns:
            生成された画像のファイルパス
        """
        if use_japanese:
            # 日本語タイトルをそのまま使用
            prompt = self._create_japanese_prompt(title, tags)
        else:
            # 英語プロンプトを生成
            prompt = self._create_prompt_from_title(title, tags)
        return self.generate(prompt)

    def _create_japanese_prompt(self, title: str, tags: List[str] = None) -> str:
        """タイトル内容に沿ったブランド統一サムネイルを生成

        戦略:
        - タイトルをそのままGeminiに渡し、内容に最適なシーンを生成させる
        - ブランドテンプレート（ダーク背景・シネマティック照明）で統一感を維持
        """
        tag_str = ', '.join(tags[:5]) if tags else ''

        prompt = f"""Generate a premium tech blog thumbnail image for this article:
Title: "{title}"
Tags: {tag_str}

IMPORTANT: The visual must directly represent the article's specific topic.
For example:
- An article about cloud market share → server racks, cloud icons, competing brand colors
- An article about a security breach → dark terminal, warning lights, broken shield
- An article about a new AI model → AI chat interface, neural network visualization
- An article about programming language trends → code editor with the specific language

Choose the most fitting photorealistic scene that a reader would immediately associate with this article's topic.

COMPOSITION:
- Dark background (deep navy/charcoal #0a1628) for the entire image
- Main visual element positioned in the center-left area
- Right third of image is darker/emptier (note.com overlays article title here)
- Cinematic depth of field: sharp focal point with soft bokeh background

BRAND STYLE (consistent across all thumbnails):
- Color palette: always dark navy base (#0a1628) with colored accents
- Photorealistic 3D render style, NOT flat illustration
- Cinematic lighting with strong rim light from behind
- Subtle lens flare or light leak for premium feel
- Slight vignette darkening at edges

STRICT RULES:
- ABSOLUTELY NO text, letters, numbers, words, or watermarks
- NO cartoon, manga, anime, or illustrated style
- NO human faces or hands
- Photorealistic or 3D render quality only

Dimensions: {self.NOTE_THUMBNAIL_WIDTH}x{self.NOTE_THUMBNAIL_HEIGHT} pixels, landscape 1.91:1."""

        return prompt

    def _create_prompt_from_title(self, title: str, tags: List[str] = None) -> str:
        """記事タイトルから画像生成プロンプトを作成"""
        # タグがあれば追加
        tag_str = ""
        if tags:
            tag_str = f" Keywords: {', '.join(tags[:5])}"

        # 基本プロンプト（英語で画像の概念を説明）
        prompt = f"""Create a tech blog thumbnail image for: "{title}".{tag_str}

Image specifications:
- Dimensions: {self.NOTE_THUMBNAIL_WIDTH}x{self.NOTE_THUMBNAIL_HEIGHT} pixels (landscape)
- Aspect ratio: 1.91:1 (blog thumbnail format)

Design requirements:
- Modern, professional tech blog aesthetic
- Vibrant gradients and eye-catching colors
- Abstract visual representation of the topic
- NO text or letters in the image
- Clean, simple composition"""

        return prompt


if __name__ == "__main__":
    # テスト実行
    generator = ThumbnailGenerator()

    # 日本語タイトルでテスト
    test_title = "Claude 4が登場！AIの新時代が始まる"
    test_tags = ["AI", "Claude", "Anthropic", "LLM"]

    print(f"テストタイトル: {test_title}")
    print(f"タグ: {test_tags}")

    result = generator.generate_from_article(test_title, test_tags)

    if result:
        print(f"\nテスト成功: {result}")
    else:
        print("\nテスト失敗")
