"""記事生成モジュール - Anthropic APIを使用して記事を生成"""

import os
import anthropic
from pydantic import BaseModel
from dotenv import load_dotenv
from .topic_collector import Topic

load_dotenv()


class Article(BaseModel):
    """生成された記事"""
    title: str
    content: str  # マークダウン形式
    tags: list[str] = []  # ハッシュタグ
    thumbnail_prompt: str = ""  # サムネイル画像生成用プロンプト（英語）


class ArticleGenerator:
    """Anthropic APIを使用して記事を生成するクラス"""

    MODELS = {
        "opus": "claude-opus-4-5-20251101",
        "sonnet": "claude-sonnet-4-5-20250929",
        "haiku": "claude-3-5-haiku-20241022",
    }

    def __init__(self, model: str = None):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        model_key = model or os.getenv("USE_MODEL", "haiku")
        self.model = self.MODELS.get(model_key, self.MODELS["haiku"])
        print(f"使用モデル: {self.model}")

    SYSTEM_PROMPT = """あなたはテクノロジー分野で人気の技術ブロガー兼エンジニアライターです。

【得意分野】
- AI・機械学習（ChatGPT, Claude, LLM全般）
- プログラミング言語（Python, JavaScript, Rust, Goなど）
- Web開発（フロントエンド、バックエンド、フレームワーク）
- DevOps・クラウド（AWS, Docker, Kubernetes）
- セキュリティ（脆弱性、対策、最新の脅威）
- テック業界のトレンドとビジネス

【あなたの記事の特徴】
- 技術的に正確でありながら、初心者にもわかりやすい説明
- ユーモアと具体的な例えを交えた親しみやすい文体
- 「なるほど！」「これは使える！」と思わせる実践的な内容
- トピックに応じて、コード例やハンズオン的な解説も含める
- 有料記事として価値のある深い考察と独自の視点
- 読者がすぐに試せる具体的なアクションポイント

【記事のトーン】
- 堅すぎず、カジュアルすぎない、プロフェッショナルな親しみやすさ
- 読者と同じ目線で、一緒に学んでいくスタンス
- 批評的になりすぎず、建設的で前向きな視点"""

    def generate(self, topic: Topic) -> Article:
        """トピックから記事を生成"""
        prompt = self._build_prompt(topic)

        print(f"記事を生成中...")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # レスポンスからテキストを取得
        raw_content = response.content[0].text

        # タイトル、タグ、サムネイルプロンプト、本文を分離
        title, tags, thumbnail_prompt, content = self._parse_response(raw_content)

        return Article(title=title, content=content, tags=tags, thumbnail_prompt=thumbnail_prompt)

    def _build_prompt(self, topic: Topic) -> str:
        """記事生成用のプロンプトを構築"""
        # カテゴリに応じた追加指示
        category_hints = {
            "ai": "AI・機械学習の最新動向として、実務での活用方法や今後の展望を含めてください。",
            "programming": "プログラミングの実践的な知識として、コード例や具体的な使い方を含めると良いでしょう。",
            "web": "Web開発者向けに、実装のポイントや注意点、ベストプラクティスを含めてください。",
            "devops": "インフラ・DevOpsの観点から、運用のコツや導入時の注意点を含めてください。",
            "security": "セキュリティの観点から、対策方法や注意すべきポイントを具体的に説明してください。",
            "business": "ビジネス・キャリアの観点から、業界への影響や今後のトレンドを考察してください。",
            "column": "エンジニアの視点からの考察やコラム的な内容として、独自の見解を含めてください。",
            "tech": "テクノロジー全般のニュースとして、わかりやすく解説してください。",
        }
        category_hint = category_hints.get(topic.category, category_hints["tech"])

        return f"""以下のトピックについて、note.comに投稿する有料記事を日本語で作成してください。

## トピック情報
- タイトル: {topic.title}
- ソース: {topic.source}
- カテゴリ: {topic.category}
- リンク: {topic.link}
- 概要: {topic.summary}

## カテゴリ別の注意点
{category_hint}

## 記事の要件
1. 読者はテクノロジーに興味があるエンジニアや一般の方々です
2. 専門用語は身近な例えを使ってわかりやすく解説してください
3. 記事の長さは2000〜3500文字程度
4. マークダウン形式で記述してください
5. 親しみやすく、読んでいて「なるほど！」と思える記事にしてください
6. 有料記事として価値のある独自の考察や実践的な内容を含めてください
7. トピックに応じて、コード例、図解的な説明、具体的な手順なども含めてください
8. 以下の構成で書いてください:
   - 導入（キャッチーな書き出し、なぜこのトピックが重要か）
   - ===ここから有料===（この行を必ず入れてください）
   - 本文（トピックの詳細な解説、具体例を交えて）
   - 実践ポイント（読者がすぐに試せること、活用方法）
   - 考察（このトピックの影響や今後の展望）
   - まとめ（読者へのメッセージ）

## 出力形式
以下の形式で出力してください:

---TITLE---
[記事のタイトル（魅力的でクリックしたくなるもの、絵文字OK）]
---TAGS---
[カンマ区切りのハッシュタグ（5〜8個、#なしで記載）]
例: AI,ChatGPT,LLM,機械学習,テクノロジー,OpenAI,プログラミング,Python
---THUMBNAIL_PROMPT---
[サムネイル画像生成用の英語プロンプト（Google Whisk用）]
例: A developer working with futuristic holographic code, digital art style, blue and purple tones
---CONTENT---
[記事本文（マークダウン形式、必ず「===ここから有料===」の行を含める）]

## note.com向けフォーマットルール（必ず守ること）
- テーブル（表）は使用禁止。箇条書きや見出しで整理すること
- 見出しは ## または ### を使用（# は使わない）
- 段落間は1行空けるだけ（複数の空行は入れない）
- 箇条書きは - を使用し、項目間に空行を入れない
- 太字は **テキスト** 形式で使用OK
- コードブロックは ``` のみ使用（言語指定なし、```python などは使わない）
- インラインコードは `コード` 形式で使用OK
- コードブロックは短めに（10行以内を推奨）
- 余計な装飾（罫線 --- など）は使わない
- シンプルで読みやすいレイアウトを心がける

注意:
- 事実に基づいて書いてください。憶測は「〜と考えられます」など明示してください
- 参照元として元のニュースソースを記事末尾に記載してください
- タグは記事の内容に関連するものを幅広く選んでください
- 「===ここから有料===」の行は必ず導入部分の後に入れてください"""

    def _parse_response(self, raw: str) -> tuple[str, list[str], str, str]:
        """レスポンスをタイトル、タグ、サムネイルプロンプト、本文に分離"""
        title = ""
        tags = []
        thumbnail_prompt = ""
        content = ""

        if "---TITLE---" in raw and "---CONTENT---" in raw:
            # タイトル部分を抽出
            title_part = raw.split("---TAGS---")[0].replace("---TITLE---", "").strip() if "---TAGS---" in raw else ""
            title = title_part.strip()

            # タグ部分を抽出
            if "---TAGS---" in raw:
                after_tags = raw.split("---TAGS---")[1]
                if "---THUMBNAIL_PROMPT---" in after_tags:
                    tags_part = after_tags.split("---THUMBNAIL_PROMPT---")[0].strip()
                elif "---CONTENT---" in after_tags:
                    tags_part = after_tags.split("---CONTENT---")[0].strip()
                else:
                    tags_part = after_tags.strip()
                tags = [t.strip().replace("#", "") for t in tags_part.split(",") if t.strip()]

            # サムネイルプロンプト部分を抽出
            if "---THUMBNAIL_PROMPT---" in raw:
                after_thumbnail = raw.split("---THUMBNAIL_PROMPT---")[1]
                if "---CONTENT---" in after_thumbnail:
                    thumbnail_prompt = after_thumbnail.split("---CONTENT---")[0].strip()
                else:
                    thumbnail_prompt = after_thumbnail.strip()

            # コンテンツ部分を抽出
            if "---CONTENT---" in raw:
                content = raw.split("---CONTENT---")[1].strip()

        else:
            # フォールバック: 最初の行をタイトルとして扱う
            lines = raw.strip().split("\n")
            title = lines[0].replace("#", "").strip()
            content = "\n".join(lines[1:]).strip()

        return title, tags, thumbnail_prompt, content


if __name__ == "__main__":
    # テスト実行
    from .topic_collector import TopicCollector

    collector = TopicCollector()
    topic = collector.select_best_topic()

    if topic:
        generator = ArticleGenerator()
        article = generator.generate(topic)

        print("\n" + "=" * 50)
        print(f"タイトル: {article.title}")
        print("=" * 50)
        print(article.content)
