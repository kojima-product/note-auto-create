"""投稿済みトピック管理モジュール"""

import json
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

    def is_posted(self, url: str) -> bool:
        """指定URLのトピックが投稿済みかどうか"""
        return url in [t["url"] for t in self.posted["topics"]]

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

    def get_posted_count(self) -> int:
        """投稿済みトピック数を取得"""
        return len(self.posted["topics"])
