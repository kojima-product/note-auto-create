"""投稿済みトピック管理モジュール"""

import json
import re
from pathlib import Path
from datetime import datetime


class PostedTracker:
    """投稿済みトピックを追跡するクラス"""

    def __init__(self, data_file: str = "data/posted_topics.json"):
        self.data_file = Path(data_file)
        if not self.data_file.parent.exists():
            self.data_file.parent.mkdir(parents=True)
        self.posted = self._load()

    def _load(self) -> dict:
        """投稿済みデータを読み込む"""
        if self.data_file.exists():
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"topics": []}

    def _save(self) -> None:
        """投稿済みデータを保存"""
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.posted, f, ensure_ascii=False, indent=2)

    def _normalize_title(self, title: str) -> str:
        """タイトルを正規化（比較用）"""
        # 記号・スペースを除去、小文字化
        normalized = re.sub(r'[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', '', title.lower())
        return normalized

    def _calculate_similarity(self, title1: str, title2: str) -> float:
        """2つのタイトルの類似度を計算（0.0〜1.0）"""
        norm1 = self._normalize_title(title1)
        norm2 = self._normalize_title(title2)

        if not norm1 or not norm2:
            return 0.0

        # 短い方をベースに共通文字列の割合を計算
        shorter = norm1 if len(norm1) <= len(norm2) else norm2
        longer = norm2 if len(norm1) <= len(norm2) else norm1

        # 共通の文字数をカウント
        common_chars = sum(1 for c in shorter if c in longer)
        similarity = common_chars / len(shorter) if shorter else 0.0

        return similarity

    def is_posted(self, url: str) -> bool:
        """指定URLのトピックが投稿済みかどうか"""
        return url in [t["url"] for t in self.posted["topics"]]

    def is_similar_posted(self, title: str, threshold: float = 0.7) -> bool:
        """類似タイトルのトピックが投稿済みかどうか"""
        for posted_topic in self.posted["topics"]:
            posted_title = posted_topic.get("title", "")
            similarity = self._calculate_similarity(title, posted_title)
            if similarity >= threshold:
                print(f"  類似トピック検出: {posted_title[:40]}... (類似度: {similarity:.2f})")
                return True
        return False

    def mark_as_posted(self, url: str, title: str) -> None:
        """トピックを投稿済みとしてマーク"""
        if not self.is_posted(url):
            self.posted["topics"].append({
                "url": url,
                "title": title,
                "posted_at": datetime.now().isoformat()
            })
            self._save()
            print(f"  投稿済みとして記録: {title[:30]}...")

    def get_posted_urls(self) -> list[str]:
        """投稿済みURLのリストを取得"""
        return [t["url"] for t in self.posted["topics"]]

    def get_posted_titles(self) -> list[str]:
        """投稿済みタイトルのリストを取得"""
        return [t["title"] for t in self.posted["topics"]]

    def get_posted_count(self) -> int:
        """投稿済みトピック数を取得"""
        return len(self.posted["topics"])
