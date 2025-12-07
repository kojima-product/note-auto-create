# note-auto-create

AI/プログラミング関連のニュースから自動で記事を生成し、noteに投稿するツール

## 機能

1. **トピック収集**: RSSフィードとWeb検索から最新ニュースを自動取得
2. **記事生成**: Anthropic API (Claude) を使用して記事を自動生成
3. **note投稿**: Playwrightでブラウザを自動操作し、有料記事として投稿
4. **重複防止**: 投稿済みトピックを記録し、同じ記事を投稿しない
5. **自動化対応**: GitHub Actionsで毎日自動実行可能

## セットアップ

### 1. 依存関係のインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. 環境変数の設定

`.env.example` をコピーして `.env` を作成:

```bash
cp .env.example .env
```

`.env` を編集:

```
ANTHROPIC_API_KEY=your_api_key_here
NOTE_EMAIL=your_email@example.com
NOTE_PASSWORD=your_password_here
USE_MODEL=sonnet
TAVILY_API_KEY=your_tavily_api_key  # オプション（Web検索用）
```

## 使い方

### 基本的な使い方

```bash
# 1記事を作成して投稿
python -m src.main --model sonnet

# 5記事を作成して投稿
python -m src.main --model sonnet --count 5

# 記事生成のみ（投稿しない）
python -m src.main --dry-run

# ブラウザを非表示で実行
python -m src.main --headless
```

### オプション一覧

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--model` | 使用するモデル (opus/sonnet/haiku) | 環境変数 or haiku |
| `--count` | 作成する記事の数 | 1 |
| `--interval` | 記事間の待機時間（秒） | 60 |
| `--price` | 有料記事の価格（円） | 100 |
| `--headless` | ブラウザを非表示で実行 | False |
| `--dry-run` | 投稿せずに記事生成のみ | False |
| `--no-web-search` | Web検索を無効化 | False |
| `--test-login` | ログインテストのみ | - |

## GitHub Actions で自動化

毎日自動で5記事を投稿するワークフローが含まれています。

### セットアップ

1. GitHubリポジトリの Settings > Secrets and variables > Actions で以下を設定:

   - `ANTHROPIC_API_KEY`: Anthropic APIキー
   - `NOTE_EMAIL`: noteのログインメールアドレス
   - `NOTE_PASSWORD`: noteのパスワード
   - `TAVILY_API_KEY`: Tavily APIキー（オプション）

2. リポジトリをプッシュすると、毎日UTC 0:00（日本時間9:00）に自動実行されます

### 手動実行

GitHub Actions > Daily Note Auto Post > Run workflow から手動実行も可能です。
記事数やモデルを指定できます。

## プロジェクト構成

```
note-auto-create/
├── .github/
│   └── workflows/
│       └── daily-post.yml    # GitHub Actions ワークフロー
├── src/
│   ├── main.py               # エントリーポイント
│   ├── topic_collector.py    # トピック収集（RSS + Web検索）
│   ├── article_generator.py  # Claude APIで記事生成
│   ├── note_publisher.py     # Playwrightでnote投稿
│   ├── web_searcher.py       # Web検索（Tavily API）
│   └── posted_tracker.py     # 投稿済み管理
├── config/
│   └── feeds.yaml            # RSSフィード設定
├── data/
│   └── posted_topics.json    # 投稿済みトピック記録
├── output/                    # 生成記事のバックアップ
├── .env                       # 環境変数（git管理外）
├── .env.example
├── requirements.txt
└── README.md
```

## 対応トピック

- AI・機械学習（ChatGPT, Claude, Gemini, LLMなど）
- プログラミング言語（Python, JavaScript, Rust, Goなど）
- Web開発（React, Next.js, フロントエンド, バックエンド）
- DevOps・クラウド（AWS, Docker, Kubernetes）
- セキュリティ
- テック業界ニュース・スタートアップ

## カスタマイズ

### RSSフィードの追加/削除

`config/feeds.yaml` を編集してフィードを管理できます。

### Web検索クエリの変更

`src/web_searcher.py` の `SEARCH_QUERIES` を編集できます。

## 注意事項

- noteは公式APIを提供していないため、UI変更により動作しなくなる可能性があります
- 本ツールの使用は自己責任でお願いします
- noteの利用規約を遵守してください
- API利用料金が発生します（Anthropic API, Tavily API）
