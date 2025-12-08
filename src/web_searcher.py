"""Web検索モジュール - 最新のAI/プログラミングニュースを検索"""

import os
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class SearchResult(BaseModel):
    """検索結果"""
    title: str
    url: str
    content: str
    score: float = 0.0
    published_date: Optional[str] = None


class WebSearcher:
    """Web検索でトピックを取得するクラス"""

    # 多様なトピックの検索クエリ（2025年12月の最新ニュースを取得）
    SEARCH_QUERIES = [
        # AI・機械学習（2025年最新）
        "AI 人工知能 最新ニュース 2025年12月",
        "ChatGPT OpenAI 新機能 2025年",
        "Claude Anthropic 最新 2025年",
        "Google Gemini AI 新機能 2025",
        "LLM 大規模言語モデル 最新 2025年",
        "生成AI 新サービス 発表 2025",

        # プログラミング言語・フレームワーク（2025年最新）
        "Python 最新 リリース 2025年",
        "JavaScript TypeScript 最新 2025",
        "React Next.js 新機能 2025年",
        "Rust Go 言語 最新 2025",
        "プログラミング 開発者ツール 2025年",

        # Web開発（2025年最新）
        "フロントエンド 開発 トレンド 2025年",
        "バックエンド API 新技術 2025",
        "Web開発 フレームワーク 2025年",

        # DevOps・クラウド（2025年最新）
        "AWS 新サービス 発表 2025年12月",
        "Azure GCP 最新 2025年",
        "Docker Kubernetes 新機能 2025",
        "クラウド インフラ 新サービス 2025年",

        # セキュリティ（2025年最新）
        "サイバーセキュリティ 脆弱性 2025年",
        "セキュリティ インシデント 2025年12月",

        # ビジネス・トレンド（2025年最新）
        "テック スタートアップ 資金調達 2025年",
        "IT企業 ニュース 2025年12月",
        "テクノロジー業界 動向 2025",

        # その他（2025年最新）
        "ガジェット 新製品 2025年",
        "オープンソース 新プロジェクト 2025",
        "テック ニュース 話題 2025年12月",
    ]

    def __init__(self):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.enabled = bool(self.tavily_api_key)

        if not self.enabled:
            print("注意: TAVILY_API_KEYが設定されていないため、Web検索は無効です")
            print("  RSSフィードからのトピック収集のみ使用します")

    def search(self, query: str = None, max_results: int = 5) -> list[SearchResult]:
        """Web検索を実行"""
        if not self.enabled:
            return []

        try:
            from tavily import TavilyClient
        except ImportError:
            print("警告: tavilyパッケージがインストールされていません")
            print("  pip install tavily-python でインストールしてください")
            return []

        if not query:
            # ランダムに検索クエリを選択
            import random
            query = random.choice(self.SEARCH_QUERIES)

        print(f"Web検索中: {query}")

        try:
            client = TavilyClient(api_key=self.tavily_api_key)
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=max_results,
                include_answer=False,
                include_raw_content=False,
                days=3,  # 過去3日間に限定（より新鮮なニュース）
            )

            results = []
            for item in response.get("results", []):
                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", "")[:500],
                    score=item.get("score", 0.0),
                    published_date=item.get("published_date"),
                )
                results.append(result)

            print(f"  {len(results)}件の結果を取得")
            return results

        except Exception as e:
            print(f"Web検索エラー: {e}")
            return []

    def search_multiple(self, max_results_per_query: int = 3, num_queries: int = 5) -> list[SearchResult]:
        """複数のクエリで検索して結果を統合（ランダムに選択）"""
        if not self.enabled:
            return []

        import random
        all_results = []
        seen_urls = set()

        # ランダムにクエリを選択（多様なトピックをカバー）
        selected_queries = random.sample(
            self.SEARCH_QUERIES,
            min(num_queries, len(self.SEARCH_QUERIES))
        )

        for query in selected_queries:
            results = self.search(query, max_results=max_results_per_query)
            for result in results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    all_results.append(result)

        # スコアでソート
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results


if __name__ == "__main__":
    # テスト実行
    searcher = WebSearcher()
    if searcher.enabled:
        results = searcher.search_multiple()
        print(f"\n取得した結果: {len(results)}件")
        for r in results[:5]:
            print(f"  - {r.title}")
            print(f"    URL: {r.url}")
            print(f"    スコア: {r.score}")
