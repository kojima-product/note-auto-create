"""メール通知モジュール - Gmail SMTPで記事作成完了を通知"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class EmailNotifier:
    """Gmailで通知メールを送信するクラス"""

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

    def __init__(self):
        self.sender_email = os.getenv("GMAIL_ADDRESS")
        self.app_password = os.getenv("GMAIL_APP_PASSWORD")
        self.recipient_email = os.getenv("NOTIFY_EMAIL") or self.sender_email

        self.enabled = bool(self.sender_email and self.app_password)

        if not self.enabled:
            print("注意: メール通知が無効です（GMAIL_ADDRESS, GMAIL_APP_PASSWORDを設定してください）")

    def send_notification(
        self,
        article_title: str,
        article_url: str = None,
        success: bool = True,
        details: str = None
    ) -> bool:
        """記事作成完了の通知メールを送信"""
        if not self.enabled:
            return False

        try:
            # メール作成
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"{'✅' if success else '❌'} note記事作成{'完了' if success else '失敗'}: {article_title[:30]}..."
            msg["From"] = self.sender_email
            msg["To"] = self.recipient_email

            # 本文作成
            timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M")

            text_content = f"""
note自動記事作成 {'完了' if success else '失敗'}通知

日時: {timestamp}
タイトル: {article_title}
ステータス: {'成功' if success else '失敗'}
"""
            if article_url:
                text_content += f"URL: {article_url}\n"
            if details:
                text_content += f"\n詳細:\n{details}\n"

            html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
    <h2 style="color: {'#28a745' if success else '#dc3545'};">
        {'✅' if success else '❌'} note記事作成{'完了' if success else '失敗'}
    </h2>
    <table style="border-collapse: collapse; margin: 20px 0;">
        <tr>
            <td style="padding: 8px; font-weight: bold;">日時:</td>
            <td style="padding: 8px;">{timestamp}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold;">タイトル:</td>
            <td style="padding: 8px;">{article_title}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold;">ステータス:</td>
            <td style="padding: 8px; color: {'#28a745' if success else '#dc3545'};">
                {'成功' if success else '失敗'}
            </td>
        </tr>
        {"<tr><td style='padding: 8px; font-weight: bold;'>URL:</td><td style='padding: 8px;'><a href='" + article_url + "'>" + article_url + "</a></td></tr>" if article_url else ""}
    </table>
    {f"<p style='color: #666;'>{details}</p>" if details else ""}
    <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
    <p style="color: #999; font-size: 12px;">
        このメールはnote-auto-createから自動送信されました。
    </p>
</body>
</html>
"""
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # SMTP送信
            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, self.recipient_email, msg.as_string())

            print(f"  通知メール送信完了: {self.recipient_email}")
            return True

        except Exception as e:
            print(f"  メール送信エラー: {e}")
            return False

    def send_daily_summary(
        self,
        success_count: int,
        fail_count: int,
        articles: list[dict]
    ) -> bool:
        """1日の投稿サマリーを送信（パフォーマンスデータ付き）"""
        if not self.enabled:
            return False

        try:
            from .performance_analyzer import PerformanceAnalyzer
            analyzer = PerformanceAnalyzer()
        except Exception:
            analyzer = None

        try:
            total = success_count + fail_count
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"📊 note記事 日次レポート: {success_count}/{total}件成功"
            msg["From"] = self.sender_email
            msg["To"] = self.recipient_email

            timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M")

            # 記事リスト
            article_list_text = "\n".join([
                f"  {'✅' if a.get('success') else '❌'} {a.get('title', '不明')}"
                for a in articles
            ])

            article_list_html = "".join([
                f"<li style='color: {'#28a745' if a.get('success') else '#dc3545'};'>{a.get('title', '不明')}</li>"
                for a in articles
            ])

            # Performance section
            perf_text = ""
            perf_html = ""
            recommendations = []
            if analyzer and analyzer.stats:
                trend = analyzer.get_recent_trend()
                best = analyzer.get_best_performing_articles(3)
                cat_perf = analyzer.get_category_performance()

                perf_text = f"""
パフォーマンス概要（直近7日間）:
  記事数: {trend['recent_count']}
  平均PV: {trend['recent_avg_views']:.0f} (前期比: {trend['views_change_pct']:+.1f}%)
  売上合計: {trend['recent_total_revenue']}円
"""
                if best:
                    perf_text += "\nベスト記事:\n"
                    for i, a in enumerate(best, 1):
                        perf_text += f"  {i}. {a['title'][:40]}... (PV={a.get('views', 0)}, スキ={a.get('likes', 0)})\n"

                # Generate recommendations
                if cat_perf:
                    sorted_cats = sorted(cat_perf.items(), key=lambda x: x[1]["avg_views"], reverse=True)
                    if sorted_cats:
                        top_cat = sorted_cats[0][0]
                        recommendations.append(f"「{top_cat}」カテゴリのPVが高いため、このカテゴリの記事を増やすと効果的です")
                    if len(sorted_cats) > 1:
                        low_cat = sorted_cats[-1][0]
                        if sorted_cats[-1][1]["avg_views"] < sorted_cats[0][1]["avg_views"] * 0.3:
                            recommendations.append(f"「{low_cat}」カテゴリのPVが低めです。品質向上か頻度調整を検討してください")

                if trend["views_change_pct"] > 20:
                    recommendations.append("PVが上昇トレンドです。現在の方針を維持してください")
                elif trend["views_change_pct"] < -20:
                    recommendations.append("PVが下降トレンドです。トピック選定やタイトルの見直しを検討してください")

                if recommendations:
                    perf_text += "\n推奨アクション:\n"
                    for rec in recommendations:
                        perf_text += f"  - {rec}\n"

                # HTML performance section
                perf_html = f"""
    <h3>📈 パフォーマンス概要（直近7日間）</h3>
    <div style="margin: 10px 0; padding: 15px; background: #f0f7ff; border-radius: 8px;">
        <p><strong>記事数:</strong> {trend['recent_count']} |
           <strong>平均PV:</strong> {trend['recent_avg_views']:.0f}
           <span style="color: {'#28a745' if trend['views_change_pct'] >= 0 else '#dc3545'};">
               ({trend['views_change_pct']:+.1f}%)
           </span> |
           <strong>売上合計:</strong> {trend['recent_total_revenue']}円
        </p>
    </div>
"""
                if best:
                    perf_html += "<h4>ベスト記事</h4><ol>"
                    for a in best:
                        perf_html += f"<li>{a['title'][:50]}... (PV={a.get('views', 0)}, スキ={a.get('likes', 0)})</li>"
                    perf_html += "</ol>"

                if recommendations:
                    perf_html += "<h4>💡 推奨アクション</h4><ul>"
                    for rec in recommendations:
                        perf_html += f"<li>{rec}</li>"
                    perf_html += "</ul>"

            text_content = f"""
note自動記事作成 日次レポート

日時: {timestamp}
成功: {success_count}件
失敗: {fail_count}件

作成した記事:
{article_list_text}
{perf_text}
"""

            html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
    <h2>📊 note記事 日次レポート</h2>
    <p style="color: #666;">{timestamp}</p>
    <div style="margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 8px;">
        <span style="font-size: 24px; color: #28a745; margin-right: 20px;">
            ✅ 成功: {success_count}件
        </span>
        <span style="font-size: 24px; color: #dc3545;">
            ❌ 失敗: {fail_count}件
        </span>
    </div>
    <h3>作成した記事</h3>
    <ul>
        {article_list_html}
    </ul>
    {perf_html}
    <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
    <p style="color: #999; font-size: 12px;">
        このメールはnote-auto-createから自動送信されました。
    </p>
</body>
</html>
"""
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, self.recipient_email, msg.as_string())

            print(f"日次レポート送信完了: {self.recipient_email}")
            return True

        except Exception as e:
            print(f"日次レポート送信エラー: {e}")
            return False

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

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "📊 note記事 週次パフォーマンスレポート"
            msg["From"] = self.sender_email
            msg["To"] = self.recipient_email

            summary = analyzer.generate_summary()
            timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M")

            # Category performance for HTML
            cat_perf = analyzer.get_category_performance()
            cat_html_rows = ""
            for cat, data in sorted(cat_perf.items(), key=lambda x: x[1]["avg_views"], reverse=True):
                cat_html_rows += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{cat}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{data['avg_views']:.0f}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{data['avg_likes']:.1f}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{data['avg_purchases']:.1f}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{data['avg_revenue']:.0f}円</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{data['count']}</td>
                </tr>"""

            # Best articles
            best = analyzer.get_best_performing_articles(5)
            best_html = ""
            for i, a in enumerate(best, 1):
                best_html += f"<li><strong>{a['title'][:50]}...</strong> (PV={a.get('views', 0)}, スキ={a.get('likes', 0)}, 購入={a.get('purchases', 0)})</li>"

            # Trend
            trend = analyzer.get_recent_trend()

            # Free vs Paid
            fp = analyzer.get_free_vs_paid_performance()
            fp_html = ""
            for group, data in fp.items():
                label = "無料" if group == "free" else "有料"
                fp_html += f"<p><strong>{label}:</strong> PV平均={data['avg_views']:.0f}, スキ平均={data['avg_likes']:.1f}"
                if group == "paid":
                    fp_html += f", 購入平均={data.get('avg_purchases', 0):.1f}, 売上平均={data.get('avg_revenue', 0):.0f}円"
                fp_html += f" ({data['count']}記事)</p>"

            text_content = f"""
note記事 週次パフォーマンスレポート
{timestamp}

{summary}
"""

            html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px; max-width: 700px; margin: 0 auto;">
    <h2>📊 note記事 週次パフォーマンスレポート</h2>
    <p style="color: #666;">{timestamp}</p>

    <div style="margin: 20px 0; padding: 15px; background: #f0f7ff; border-radius: 8px;">
        <h3 style="margin-top: 0;">直近7日間のトレンド</h3>
        <p>記事数: <strong>{trend['recent_count']}</strong> |
           平均PV: <strong>{trend['recent_avg_views']:.0f}</strong>
           <span style="color: {'#28a745' if trend['views_change_pct'] >= 0 else '#dc3545'};">
               ({trend['views_change_pct']:+.1f}%)
           </span> |
           売上合計: <strong>{trend['recent_total_revenue']}円</strong>
        </p>
    </div>

    <h3>カテゴリ別パフォーマンス</h3>
    <table style="border-collapse: collapse; width: 100%;">
        <tr style="background: #f8f9fa;">
            <th style="padding: 8px; text-align: left;">カテゴリ</th>
            <th style="padding: 8px; text-align: right;">PV平均</th>
            <th style="padding: 8px; text-align: right;">スキ平均</th>
            <th style="padding: 8px; text-align: right;">購入平均</th>
            <th style="padding: 8px; text-align: right;">売上平均</th>
            <th style="padding: 8px; text-align: right;">記事数</th>
        </tr>
        {cat_html_rows}
    </table>

    <h3>無料 vs 有料</h3>
    {fp_html}

    <h3>ベスト記事 TOP5</h3>
    <ol>{best_html}</ol>

    <div style="margin: 20px 0; padding: 15px; background: #fff3cd; border-radius: 8px;">
        <h3 style="margin-top: 0;">データ信頼度: {analyzer.confidence:.0%}</h3>
        <p style="color: #856404;">
            {"十分なデータが蓄積されています。動的スコアリングが有効です。" if analyzer.has_sufficient_data
             else f"あと{max(0, 50 - len([a for a in analyzer.stats if a.get('views', 0) > 0]))}記事分のPVデータが必要です。"}
        </p>
    </div>

    <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
    <p style="color: #999; font-size: 12px;">
        このメールはnote-auto-createから自動送信されました。
    </p>
</body>
</html>
"""
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, self.recipient_email, msg.as_string())

            print(f"週次レポート送信完了: {self.recipient_email}")
            return True

        except Exception as e:
            print(f"週次レポート送信エラー: {e}")
            return False


if __name__ == "__main__":
    # テスト
    notifier = EmailNotifier()
    if notifier.enabled:
        notifier.send_notification(
            article_title="テスト記事タイトル",
            success=True,
            details="これはテスト通知です。"
        )
