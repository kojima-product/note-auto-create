"""パフォーマンス分析モジュール - 記事データの分析と最適化インサイト"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


DATA_DIR = Path("data")
STATS_FILE = DATA_DIR / "article_stats.json"
POSTED_FILE = DATA_DIR / "posted_topics.json"


class PerformanceAnalyzer:
    """記事パフォーマンスを分析し、スコアリングの動的重みを提供"""

    def __init__(self):
        self.stats = self._load_stats()
        self.posted = self._load_posted()

    def _load_stats(self) -> list[dict]:
        if STATS_FILE.exists():
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("articles", [])
        return []

    def _load_posted(self) -> list[dict]:
        if POSTED_FILE.exists():
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("topics", [])
        return []

    @property
    def has_sufficient_data(self) -> bool:
        """Enough data for performance-based scoring (50+ articles with stats)"""
        articles_with_views = [a for a in self.stats if a.get("views", 0) > 0]
        return len(articles_with_views) >= 50

    @property
    def confidence(self) -> float:
        """Confidence factor: 0.0 (no data) to 1.0 (50+ articles)"""
        articles_with_views = [a for a in self.stats if a.get("views", 0) > 0]
        return min(len(articles_with_views) / 50, 1.0)

    def get_category_performance(self) -> dict[str, dict]:
        """Calculate average performance per category

        Returns:
            Dict of category -> {avg_views, avg_likes, avg_purchases, avg_revenue, count}
        """
        category_stats = defaultdict(lambda: {"views": [], "likes": [], "purchases": [], "revenue": []})

        for article in self.stats:
            category = article.get("category", "unknown")
            if not category:
                category = "unknown"
            category_stats[category]["views"].append(article.get("views", 0))
            category_stats[category]["likes"].append(article.get("likes", 0))
            category_stats[category]["purchases"].append(article.get("purchases", 0))
            category_stats[category]["revenue"].append(article.get("revenue", 0))

        result = {}
        for cat, data in category_stats.items():
            count = len(data["views"])
            result[cat] = {
                "avg_views": sum(data["views"]) / count if count else 0,
                "avg_likes": sum(data["likes"]) / count if count else 0,
                "avg_purchases": sum(data["purchases"]) / count if count else 0,
                "avg_revenue": sum(data["revenue"]) / count if count else 0,
                "count": count,
            }

        return result

    def get_tag_performance(self) -> dict[str, dict]:
        """Calculate performance per tag"""
        tag_stats = defaultdict(lambda: {"views": [], "likes": [], "purchases": []})

        for article in self.stats:
            tags = article.get("tags", [])
            for tag in tags:
                tag_stats[tag]["views"].append(article.get("views", 0))
                tag_stats[tag]["likes"].append(article.get("likes", 0))
                tag_stats[tag]["purchases"].append(article.get("purchases", 0))

        result = {}
        for tag, data in tag_stats.items():
            count = len(data["views"])
            result[tag] = {
                "avg_views": sum(data["views"]) / count if count else 0,
                "avg_likes": sum(data["likes"]) / count if count else 0,
                "avg_purchases": sum(data["purchases"]) / count if count else 0,
                "count": count,
            }

        return result

    def get_day_of_week_performance(self) -> dict[str, dict]:
        """Calculate performance by day of week"""
        dow_stats = defaultdict(lambda: {"views": [], "likes": [], "purchases": []})
        dow_names = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]

        for article in self.stats:
            posted_at = article.get("posted_at", "")
            if not posted_at:
                continue
            try:
                dt = datetime.fromisoformat(posted_at)
                dow = dow_names[dt.weekday()]
                dow_stats[dow]["views"].append(article.get("views", 0))
                dow_stats[dow]["likes"].append(article.get("likes", 0))
                dow_stats[dow]["purchases"].append(article.get("purchases", 0))
            except (ValueError, IndexError):
                continue

        result = {}
        for dow, data in dow_stats.items():
            count = len(data["views"])
            result[dow] = {
                "avg_views": sum(data["views"]) / count if count else 0,
                "avg_likes": sum(data["likes"]) / count if count else 0,
                "avg_purchases": sum(data["purchases"]) / count if count else 0,
                "count": count,
            }

        return result

    def get_free_vs_paid_performance(self) -> dict[str, dict]:
        """Compare free vs paid article performance"""
        groups = {"free": {"views": [], "likes": []}, "paid": {"views": [], "likes": [], "purchases": [], "revenue": []}}

        for article in self.stats:
            is_free = article.get("is_free", True)
            key = "free" if is_free else "paid"
            groups[key]["views"].append(article.get("views", 0))
            groups[key]["likes"].append(article.get("likes", 0))
            if not is_free:
                groups[key]["purchases"].append(article.get("purchases", 0))
                groups[key]["revenue"].append(article.get("revenue", 0))

        result = {}
        for group, data in groups.items():
            count = len(data["views"])
            entry = {
                "avg_views": sum(data["views"]) / count if count else 0,
                "avg_likes": sum(data["likes"]) / count if count else 0,
                "count": count,
            }
            if group == "paid":
                entry["avg_purchases"] = sum(data["purchases"]) / count if count else 0
                entry["avg_revenue"] = sum(data["revenue"]) / count if count else 0
            result[group] = entry

        return result

    def get_category_score_weights(self) -> dict[str, float]:
        """Generate dynamic score weights per category based on performance

        Returns:
            Dict of category -> weight (0-30 range, matching current scoring scale)
        """
        cat_perf = self.get_category_performance()
        if not cat_perf:
            return {}

        # Composite score: views * 1 + likes * 5 + purchases * 20
        scores = {}
        for cat, data in cat_perf.items():
            scores[cat] = (
                data["avg_views"] * 1.0
                + data["avg_likes"] * 5.0
                + data["avg_purchases"] * 20.0
            )

        if not scores:
            return {}

        # Normalize to 0-30 range
        max_score = max(scores.values()) if scores else 1
        if max_score == 0:
            return {cat: 10.0 for cat in scores}

        weights = {}
        for cat, score in scores.items():
            weights[cat] = (score / max_score) * 30.0

        return weights

    def get_best_performing_articles(self, n: int = 10) -> list[dict]:
        """Get top N performing articles by composite score"""
        scored = []
        for article in self.stats:
            score = (
                article.get("views", 0) * 1.0
                + article.get("likes", 0) * 5.0
                + article.get("purchases", 0) * 20.0
            )
            scored.append({**article, "_score": score})

        scored.sort(key=lambda x: x["_score"], reverse=True)
        return scored[:n]

    def get_recent_trend(self, days: int = 7) -> dict:
        """Get performance trend for recent days"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        older = []

        for article in self.stats:
            posted_at = article.get("posted_at", "")
            if not posted_at:
                continue
            try:
                dt = datetime.fromisoformat(posted_at)
                if dt >= cutoff:
                    recent.append(article)
                else:
                    older.append(article)
            except ValueError:
                continue

        def _avg(articles, key):
            vals = [a.get(key, 0) for a in articles]
            return sum(vals) / len(vals) if vals else 0

        recent_views = _avg(recent, "views")
        older_views = _avg(older, "views")

        return {
            "recent_count": len(recent),
            "older_count": len(older),
            "recent_avg_views": recent_views,
            "older_avg_views": older_views,
            "views_change_pct": ((recent_views - older_views) / older_views * 100) if older_views > 0 else 0,
            "recent_total_revenue": sum(a.get("revenue", 0) for a in recent),
        }

    def generate_summary(self) -> str:
        """Generate a human-readable performance summary"""
        lines = []
        lines.append("=== パフォーマンスサマリー ===\n")

        # Data status
        articles_with_views = [a for a in self.stats if a.get("views", 0) > 0]
        lines.append(f"データ状況: {len(self.stats)}記事 (PVデータあり: {len(articles_with_views)})")
        lines.append(f"信頼度: {self.confidence:.0%}\n")

        # Category performance
        cat_perf = self.get_category_performance()
        if cat_perf:
            lines.append("カテゴリ別パフォーマンス:")
            sorted_cats = sorted(cat_perf.items(), key=lambda x: x[1]["avg_views"], reverse=True)
            for cat, data in sorted_cats:
                lines.append(
                    f"  {cat}: PV平均={data['avg_views']:.0f}, "
                    f"スキ平均={data['avg_likes']:.1f}, "
                    f"購入平均={data['avg_purchases']:.1f} "
                    f"({data['count']}記事)"
                )

        # Free vs Paid
        fp = self.get_free_vs_paid_performance()
        if fp:
            lines.append("\n無料 vs 有料:")
            for group, data in fp.items():
                label = "無料" if group == "free" else "有料"
                line = f"  {label}: PV平均={data['avg_views']:.0f}, スキ平均={data['avg_likes']:.1f}"
                if group == "paid":
                    line += f", 購入平均={data.get('avg_purchases', 0):.1f}, 売上平均={data.get('avg_revenue', 0):.0f}円"
                line += f" ({data['count']}記事)"
                lines.append(line)

        # Best articles
        best = self.get_best_performing_articles(5)
        if best:
            lines.append("\nベスト記事 (TOP5):")
            for i, article in enumerate(best, 1):
                lines.append(
                    f"  {i}. {article['title'][:40]}... "
                    f"(PV={article.get('views', 0)}, スキ={article.get('likes', 0)}, "
                    f"購入={article.get('purchases', 0)})"
                )

        # Trend
        trend = self.get_recent_trend()
        if trend["recent_count"] > 0:
            lines.append(f"\n直近7日間のトレンド:")
            lines.append(f"  記事数: {trend['recent_count']}")
            lines.append(f"  平均PV: {trend['recent_avg_views']:.0f} (前期比: {trend['views_change_pct']:+.1f}%)")
            lines.append(f"  売上合計: {trend['recent_total_revenue']}円")

        return "\n".join(lines)


if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    print(analyzer.generate_summary())
