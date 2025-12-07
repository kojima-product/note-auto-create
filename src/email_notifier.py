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
        """1日の投稿サマリーを送信"""
        if not self.enabled:
            return False

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

            text_content = f"""
note自動記事作成 日次レポート

日時: {timestamp}
成功: {success_count}件
失敗: {fail_count}件

作成した記事:
{article_list_text}
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


if __name__ == "__main__":
    # テスト
    notifier = EmailNotifier()
    if notifier.enabled:
        notifier.send_notification(
            article_title="テスト記事タイトル",
            success=True,
            details="これはテスト通知です。"
        )
