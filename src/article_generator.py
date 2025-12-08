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

    SYSTEM_PROMPT = """あなたはテクノロジー分野で大人気の技術ブロガー兼エンジニアライターです。
読者から「この人の記事は100円払う価値がある！」と言われる記事を書くことで有名です。

【得意分野】
- AI・機械学習（ChatGPT, Claude, LLM全般）
- プログラミング言語（Python, JavaScript, Rust, Goなど）
- Web開発（フロントエンド、バックエンド、フレームワーク）
- DevOps・クラウド（AWS, Docker, Kubernetes）
- セキュリティ（脆弱性、対策、最新の脅威）
- テック業界のトレンドとビジネス

【あなたの記事の最大の特徴】
- 難しい技術も「身近な例え」で笑いながら理解できる
  例：「AIの学習は、猫に芸を教えるようなもの。最初は全然言うこと聞かないけど、おやつ（データ）をあげ続けると覚える」
- 読者が「へぇ〜！」「マジか！」と声を出してしまう驚きの事実を必ず入れる
- 技術の「裏話」や「ぶっちゃけ話」を入れて、エンジニア同士の雑談感を出す
- 複雑な概念は図解的な説明（文字で描く図）で視覚的に理解させる
- 「明日から使える」具体的なTipsを必ず3つ以上入れる
- 読者が友達に話したくなる「豆知識」を散りばめる

【記事のトーン】
- まるで詳しい先輩エンジニアがカフェで教えてくれるような親しみやすさ
- 「〜なんですよね」「〜って知ってました？」など話しかけ口調を適度に使う
- 技術的な正確さは保ちつつ、ユーモアを忘れない
- 読者と一緒にワクワクしながら新技術を探検するスタンス
- 「これ、ヤバくないですか？」「個人的に超アツい」など感情を表現

【絶対に守ること】
- 2025年12月現在の最新情報として書く（古い情報は使わない）
- 100円の価値を感じさせる「ここでしか読めない視点」を必ず入れる
- 読み終わった後「読んでよかった！」と思わせる満足感を提供する"""

    def generate(self, topic: Topic, is_free: bool = False) -> Article:
        """トピックから記事を生成

        Args:
            topic: 記事のトピック
            is_free: 無料記事として生成する場合はTrue
        """
        prompt = self._build_prompt_free(topic) if is_free else self._build_prompt(topic)

        print(f"記事を生成中...")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
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
※重要: 現在は2025年12月です。この時点での最新情報として記事を書いてください。

## トピック情報
- タイトル: {topic.title}
- ソース: {topic.source}
- カテゴリ: {topic.category}
- リンク: {topic.link}
- 概要: {topic.summary}

## カテゴリ別の注意点
{category_hint}

## 記事の要件（100円の価値を提供する）
1. 読者は「へぇ〜！」「なるほど！」と声を出したくなる記事を期待しています
2. 難しい概念は身近な例えで説明（例：「APIは料理の出前注文みたいなもの」）
3. **重要: 記事の長さは必ず3000〜4500文字**（短すぎると100円の価値がない！）
4. マークダウン形式で記述してください
5. 以下を必ず含めてください：
   - 読者が「マジか！」と驚く事実や裏話を2〜3個
   - 明日から使える具体的なTipsを3つ以上
   - 友達に話したくなる豆知識
   - エンジニア同士の雑談のような親しみやすいトーン
6. 以下の構成で書いてください:
   - 導入（読者の興味を引くフック、「これ知ってました？」的な問いかけ）
   - ===ここから有料===（この行を必ず入れてください）
   - 本文（トピックの詳細解説、驚きの事実、具体例をたっぷり）
   - 実践Tips（「明日から使える3つのポイント」など箇条書きで）
   - ぶっちゃけ話（業界人だからわかる本音の考察）
   - まとめ（読者への熱いメッセージ）

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

    def _build_prompt_free(self, topic: Topic) -> str:
        """無料記事生成用のプロンプトを構築"""
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

        return f"""以下のトピックについて、note.comに投稿する**無料記事**を日本語で作成してください。
※重要: 現在は2025年12月です。この時点での最新情報として記事を書いてください。

## トピック情報
- タイトル: {topic.title}
- ソース: {topic.source}
- カテゴリ: {topic.category}
- リンク: {topic.link}
- 概要: {topic.summary}

## カテゴリ別の注意点
{category_hint}

## 記事の要件（無料でも価値ある記事を！）
1. 読者は「へぇ〜！」「なるほど！」と声を出したくなる記事を期待しています
2. 難しい概念は身近な例えで説明（例：「APIは料理の出前注文みたいなもの」）
3. **重要: 記事の長さは必ず2000〜3500文字**
4. マークダウン形式で記述してください
5. 以下を必ず含めてください：
   - 読者が「マジか！」と驚く事実や裏話を2〜3個
   - 明日から使える具体的なTipsを2つ以上
   - 友達に話したくなる豆知識
   - エンジニア同士の雑談のような親しみやすいトーン
6. 以下の構成で書いてください:
   - 導入（読者の興味を引くフック、「これ知ってました？」的な問いかけ）
   - 本文（トピックの詳細解説、驚きの事実、具体例をたっぷり）
   - 実践Tips（「明日から使えるポイント」など箇条書きで）
   - まとめ（読者への熱いメッセージ）

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
[記事本文（マークダウン形式）]

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
- **無料記事なので「===ここから有料===」の行は入れないでください**"""

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
