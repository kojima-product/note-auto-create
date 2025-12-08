"""トピック収集モジュール - RSSフィードとWeb検索からAI/プログラミング関連ニュースを取得"""

import feedparser
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
import time

from .web_searcher import WebSearcher


class Topic(BaseModel):
    """トピック情報"""
    title: str
    link: str
    summary: str
    published: Optional[datetime] = None
    source: str
    category: str
    language: str
    score: float = 0.0


class TopicCollector:
    """RSSフィードからトピックを収集するクラス"""

    def __init__(self, config_path: str = "config/feeds.yaml", use_web_search: bool = True):
        self.config = self._load_config(config_path)
        self.feeds = self.config.get("feeds", [])
        self.selection = self.config.get("selection", {})
        self.web_searcher = WebSearcher() if use_web_search else None

    def _load_config(self, config_path: str) -> dict:
        """設定ファイルを読み込む"""
        path = Path(config_path)
        if not path.exists():
            # プロジェクトルートからの相対パスも試す
            path = Path(__file__).parent.parent / config_path

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """エントリから日付を解析"""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return None

    def _clean_summary(self, summary: str) -> str:
        """サマリーをクリーンアップ"""
        import re
        # HTMLタグを除去
        clean = re.sub(r'<[^>]+>', '', summary)
        # 連続する空白を1つに
        clean = re.sub(r'\s+', ' ', clean)
        # 500文字で切り詰め
        return clean[:500].strip()

    def _calculate_score(self, topic: Topic) -> float:
        """トピックのスコアを計算（高いほど優先）"""
        score = 0.0

        # カテゴリ優先度
        priority_categories = self.selection.get("priority_categories", ["ai", "tech"])
        if topic.category in priority_categories:
            score += (len(priority_categories) - priority_categories.index(topic.category)) * 10

        # 言語優先度（日本語を大幅に優先）
        if topic.language == self.selection.get("priority_language", "ja"):
            score += 30

        # 新しさ（新しいほど高得点 - 今週のニュースを優先）
        if topic.published:
            age = datetime.now(timezone.utc) - topic.published
            if age < timedelta(hours=12):
                score += 25  # 12時間以内は最優先
            elif age < timedelta(hours=24):
                score += 20  # 24時間以内
            elif age < timedelta(hours=48):
                score += 15  # 48時間以内
            elif age < timedelta(days=3):
                score += 10  # 3日以内
            elif age < timedelta(days=7):
                score += 5   # 1週間以内

        # 注目キーワードで加点（多様なトピック対応）
        title_lower = topic.title.lower()

        # AI関連（高加点）
        ai_keywords = ["ai", "人工知能", "機械学習", "llm", "gpt", "claude", "生成ai",
                       "chatgpt", "openai", "anthropic", "gemini", "copilot"]
        for keyword in ai_keywords:
            if keyword in title_lower:
                score += 4
                break

        # プログラミング言語・フレームワーク
        prog_keywords = ["python", "javascript", "typescript", "rust", "go言語", "golang",
                         "react", "next.js", "vue", "node.js", "deno", "bun"]
        for keyword in prog_keywords:
            if keyword in title_lower:
                score += 3
                break

        # DevOps・クラウド
        devops_keywords = ["aws", "azure", "gcp", "docker", "kubernetes", "k8s",
                           "terraform", "ci/cd", "devops"]
        for keyword in devops_keywords:
            if keyword in title_lower:
                score += 3
                break

        # セキュリティ
        security_keywords = ["セキュリティ", "脆弱性", "攻撃", "ハッキング", "security",
                             "vulnerability", "cve"]
        for keyword in security_keywords:
            if keyword in title_lower:
                score += 3
                break

        # トレンド・注目ワード
        trend_keywords = ["新機能", "発表", "リリース", "アップデート", "launch",
                          "release", "announce", "新登場", "話題"]
        for keyword in trend_keywords:
            if keyword in title_lower:
                score += 2
                break

        return score

    def _fetch_from_web_search(self) -> list[Topic]:
        """Web検索からトピックを取得"""
        if not self.web_searcher or not self.web_searcher.enabled:
            return []

        topics = []
        results = self.web_searcher.search_multiple(max_results_per_query=3)

        for result in results:
            topic = Topic(
                title=result.title,
                link=result.url,
                summary=result.content,
                published=datetime.now(timezone.utc),  # Web検索結果は新鮮とみなす
                source="Web検索",
                category="ai",
                language="ja",
            )
            # Web検索結果のスコアを計算（days=7で取得しているため新鮮）
            topic.score = self._calculate_score(topic)
            topics.append(topic)

        return topics

    def fetch_topics(self) -> list[Topic]:
        """RSSフィードとWeb検索からトピックを取得"""
        topics = []
        max_age = timedelta(days=self.selection.get("max_age_days", 3))
        now = datetime.now(timezone.utc)

        # Web検索からトピックを取得（有効な場合）
        if self.web_searcher and self.web_searcher.enabled:
            print("Web検索からトピックを取得中...")
            web_topics = self._fetch_from_web_search()
            topics.extend(web_topics)
            print(f"  Web検索から{len(web_topics)}件取得")

        # RSSフィードからトピックを取得
        print("RSSフィードからトピックを取得中...")
        for feed_config in self.feeds:
            print(f"フィード取得中: {feed_config['name']}...")
            try:
                feed = feedparser.parse(feed_config["url"])

                for entry in feed.entries[:10]:  # 各フィードから最大10件
                    published = self._parse_date(entry)

                    # 古すぎる記事はスキップ
                    if published and (now - published) > max_age:
                        continue

                    summary = ""
                    if hasattr(entry, "summary"):
                        summary = self._clean_summary(entry.summary)
                    elif hasattr(entry, "description"):
                        summary = self._clean_summary(entry.description)

                    topic = Topic(
                        title=entry.title,
                        link=entry.link,
                        summary=summary,
                        published=published,
                        source=feed_config["name"],
                        category=feed_config["category"],
                        language=feed_config["language"],
                    )
                    topic.score = self._calculate_score(topic)
                    topics.append(topic)

                # レート制限対策
                time.sleep(0.5)

            except Exception as e:
                print(f"  エラー: {feed_config['name']} - {e}")
                continue

        return topics

    def select_best_topic(self, exclude_urls: list[str] = None, tracker=None) -> Optional[Topic]:
        """最適なトピックを1つ選択（投稿済みURLと類似タイトルを除外）"""
        topics = self.fetch_topics()

        if not topics:
            print("トピックが見つかりませんでした")
            return None

        # 投稿済みトピックを除外（URL）
        if exclude_urls:
            original_count = len(topics)
            topics = [t for t in topics if t.link not in exclude_urls]
            excluded_count = original_count - len(topics)
            if excluded_count > 0:
                print(f"  投稿済みトピック(URL)を除外: {excluded_count}件")

        # 類似タイトルのトピックを除外
        if tracker:
            original_count = len(topics)
            topics = [t for t in topics if not tracker.is_similar_posted(t.title)]
            excluded_count = original_count - len(topics)
            if excluded_count > 0:
                print(f"  類似トピック(タイトル)を除外: {excluded_count}件")

        if not topics:
            print("未投稿のトピックが見つかりませんでした")
            return None

        # スコアでソートして最高のものを選択
        topics.sort(key=lambda t: t.score, reverse=True)

        print(f"\n取得したトピック数: {len(topics)}")
        print(f"選択されたトピック: {topics[0].title}")
        print(f"  ソース: {topics[0].source}")
        print(f"  スコア: {topics[0].score}")

        return topics[0]


if __name__ == "__main__":
    # テスト実行
    collector = TopicCollector()
    topic = collector.select_best_topic()

    if topic:
        print("\n" + "=" * 50)
        print(f"タイトル: {topic.title}")
        print(f"リンク: {topic.link}")
        print(f"サマリー: {topic.summary[:200]}...")
