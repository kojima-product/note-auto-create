"""Discord通知モジュール - Webhookで記事作成完了を通知"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class DiscordNotifier:
    """Discord Webhookで通知を送信するクラス"""

    def __init__(self):
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)

        if not self.enabled:
            print("注意: Discord通知が無効です（DISCORD_WEBHOOK_URLを設定してください）")

    def _send_webhook(self, payload: dict) -> bool:
        """Send a payload to the Discord webhook"""
        if not self.enabled:
            return False

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "note-auto-create/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                # Discord returns 204 No Content on success
                return resp.status in (200, 204)
        except urllib.error.HTTPError as e:
            print(f"  Discord Webhookエラー: HTTP {e.code}")
            return False
        except Exception as e:
            print(f"  Discord送信エラー: {e}")
            return False

    def send_notification(
        self,
        article_title: str,
        article_url: str = None,
        success: bool = True,
        details: str = None,
    ) -> bool:
        """記事作成完了の通知を送信"""
        if not self.enabled:
            return False

        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M")
        status_emoji = "\u2705" if success else "\u274c"
        status_text = "投稿完了" if success else "投稿失敗"
        color = 0x28A745 if success else 0xDC3545

        embed = {
            "title": f"{status_emoji} {status_text}",
            "color": color,
            "fields": [
                {"name": "タイトル", "value": article_title, "inline": False},
                {"name": "日時", "value": timestamp, "inline": True},
            ],
            "footer": {"text": "note-auto-create"},
        }

        if article_url:
            embed["fields"].insert(
                1, {"name": "記事リンク", "value": article_url, "inline": False}
            )

        if details:
            embed["fields"].append(
                {"name": "詳細", "value": details[:1024], "inline": False}
            )

        payload = {"embeds": [embed]}
        result = self._send_webhook(payload)
        if result:
            print("  Discord通知送信完了")
        return result

    def send_daily_summary(
        self,
        success_count: int,
        fail_count: int,
        articles: list[dict],
    ) -> bool:
        """1日の投稿サマリーを送信"""
        if not self.enabled:
            return False

        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M")
        total = success_count + fail_count

        # Build article list
        article_lines = []
        for a in articles:
            emoji = "\u2705" if a.get("success") else "\u274c"
            title = a.get("title", "不明")
            url = a.get("note_url", "")
            if url:
                article_lines.append(f"{emoji} [{title}]({url})")
            else:
                article_lines.append(f"{emoji} {title}")

        article_list = "\n".join(article_lines) if article_lines else "なし"

        embed = {
            "title": f"\U0001f4ca 日次レポート: {success_count}/{total}件成功",
            "color": 0x5865F2,
            "fields": [
                {
                    "name": "結果",
                    "value": f"\u2705 成功: {success_count}件  \u274c 失敗: {fail_count}件",
                    "inline": False,
                },
                {
                    "name": "作成した記事",
                    "value": article_list[:1024],
                    "inline": False,
                },
            ],
            "footer": {"text": f"note-auto-create | {timestamp}"},
        }

        # Add performance data if available
        try:
            from .performance_analyzer import PerformanceAnalyzer

            analyzer = PerformanceAnalyzer()
            if analyzer.stats:
                trend = analyzer.get_recent_trend()
                perf_text = (
                    f"記事数: {trend['recent_count']}\n"
                    f"平均PV: {trend['recent_avg_views']:.0f} "
                    f"({trend['views_change_pct']:+.1f}%)\n"
                    f"売上合計: {trend['recent_total_revenue']}円"
                )
                embed["fields"].append(
                    {
                        "name": "\U0001f4c8 直近7日間",
                        "value": perf_text,
                        "inline": False,
                    }
                )
        except Exception:
            pass

        payload = {"embeds": [embed]}
        result = self._send_webhook(payload)
        if result:
            print("  Discord日次レポート送信完了")
        return result

    def send_weekly_report(self) -> bool:
        """週次パフォーマンスレポートを送信"""
        if not self.enabled:
            return False

        try:
            from .performance_analyzer import PerformanceAnalyzer

            analyzer = PerformanceAnalyzer()
        except Exception:
            print("パフォーマンスアナライザーの初期化に失敗しました")
            return False

        if not analyzer.stats:
            print("パフォーマンスデータがありません。週次レポートをスキップします。")
            return False

        trend = analyzer.get_recent_trend()
        best = analyzer.get_best_performing_articles(5)
        cat_perf = analyzer.get_category_performance()
        fp = analyzer.get_free_vs_paid_performance()

        # Trend embed
        trend_emoji = "\U0001f4c8" if trend["views_change_pct"] >= 0 else "\U0001f4c9"
        trend_text = (
            f"記事数: {trend['recent_count']}\n"
            f"平均PV: {trend['recent_avg_views']:.0f} "
            f"({trend['views_change_pct']:+.1f}%)\n"
            f"売上合計: {trend['recent_total_revenue']}円"
        )

        # Category performance
        cat_lines = []
        for cat, data in sorted(
            cat_perf.items(), key=lambda x: x[1]["avg_views"], reverse=True
        ):
            cat_lines.append(
                f"**{cat}**: PV={data['avg_views']:.0f} "
                f"スキ={data['avg_likes']:.1f} "
                f"購入={data['avg_purchases']:.1f} "
                f"({data['count']}記事)"
            )
        cat_text = "\n".join(cat_lines) if cat_lines else "データなし"

        # Best articles
        best_lines = []
        for i, a in enumerate(best, 1):
            best_lines.append(
                f"{i}. {a['title'][:45]}... "
                f"(PV={a.get('views', 0)}, スキ={a.get('likes', 0)})"
            )
        best_text = "\n".join(best_lines) if best_lines else "データなし"

        # Free vs Paid
        fp_lines = []
        for group, data in fp.items():
            label = "無料" if group == "free" else "有料"
            line = f"**{label}**: PV={data['avg_views']:.0f}, スキ={data['avg_likes']:.1f}"
            if group == "paid":
                line += f", 購入={data.get('avg_purchases', 0):.1f}"
            line += f" ({data['count']}記事)"
            fp_lines.append(line)
        fp_text = "\n".join(fp_lines) if fp_lines else "データなし"

        embed = {
            "title": f"{trend_emoji} 週次パフォーマンスレポート",
            "color": 0x5865F2,
            "fields": [
                {"name": "直近7日間", "value": trend_text, "inline": False},
                {
                    "name": "カテゴリ別",
                    "value": cat_text[:1024],
                    "inline": False,
                },
                {"name": "無料 vs 有料", "value": fp_text, "inline": False},
                {
                    "name": "ベスト記事 TOP5",
                    "value": best_text[:1024],
                    "inline": False,
                },
                {
                    "name": "データ信頼度",
                    "value": f"{analyzer.confidence:.0%}",
                    "inline": True,
                },
            ],
            "footer": {
                "text": f"note-auto-create | {datetime.now().strftime('%Y/%m/%d %H:%M')}"
            },
        }

        payload = {"embeds": [embed]}
        result = self._send_webhook(payload)
        if result:
            print("  Discord週次レポート送信完了")
        return result
