"""メインスクリプト - note自動記事作成"""

import argparse
import glob
import os
import random
import sys
import time
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.topic_collector import TopicCollector, Topic
from src.article_generator import ArticleGenerator
from src.note_publisher import NotePublisher
from src.posted_tracker import PostedTracker
from src.discord_notifier import DiscordNotifier
from src.thumbnail_generator import ThumbnailGenerator
from src.web_searcher import WebSearcher
from src.pricing_strategy import PricingStrategy


def validate_article_quality(article, is_free: bool) -> tuple[bool, list[str]]:
    """Pre-publish quality gate. Returns (passed, list of issues)."""
    issues = []
    content = article.content
    char_count = len(content)

    # Character count check
    min_chars = 1500 if is_free else 2500
    if char_count < min_chars:
        issues.append(f"文字数不足: {char_count}文字（最低{min_chars}文字）")

    # Paywall marker check (paid articles only)
    if not is_free:
        if "===ここから有料===" not in content:
            issues.append("有料マーカー「===ここから有料===」が見つかりません")
        else:
            # Marker position check: free preview should be 20-40% of total
            marker_pos = content.index("===ここから有料===")
            ratio = marker_pos / char_count if char_count > 0 else 0
            if ratio < 0.10:
                issues.append(f"無料プレビューが短すぎます（全体の{ratio:.0%}）")
            elif ratio > 0.50:
                issues.append(f"無料プレビューが長すぎます（全体の{ratio:.0%}）")

    # Tag count check
    if len(article.tags) < 3:
        issues.append(f"タグ不足: {len(article.tags)}個（最低3個）")

    passed = len(issues) == 0
    return passed, issues


def cleanup_generated_files():
    """生成されたファイルを削除（リポジトリを軽く保つため）"""
    project_root = Path(__file__).parent.parent
    deleted_count = 0

    # output/内のmdファイルを削除
    for md_file in glob.glob(str(project_root / "output" / "*.md")):
        try:
            os.remove(md_file)
            deleted_count += 1
        except Exception:
            pass

    # output/thumbnails/内の画像ファイルを削除
    for img_file in glob.glob(str(project_root / "output" / "thumbnails" / "*")):
        try:
            os.remove(img_file)
            deleted_count += 1
        except Exception:
            pass

    # ルートディレクトリのスクリーンショットを削除
    for pattern in ["debug_*.png", "error_*.png", "*.png", "*.jpg"]:
        for img_file in glob.glob(str(project_root / pattern)):
            # venvなどの重要なディレクトリは除外
            if "venv" not in img_file and "site-packages" not in img_file:
                try:
                    os.remove(img_file)
                    deleted_count += 1
                except Exception:
                    pass

    if deleted_count > 0:
        print(f"クリーンアップ: {deleted_count}件のファイルを削除しました")


def create_custom_topic(custom_topic: str) -> Topic:
    """カスタムトピックからTopicオブジェクトを作成

    Args:
        custom_topic: ユーザーが指定したトピック

    Returns:
        Topic: 作成されたトピックオブジェクト
    """
    from datetime import timezone

    # Web検索でカスタムトピックについて情報収集
    searcher = WebSearcher()
    search_results = searcher.search_custom_topic(custom_topic, max_results=10)

    # 検索結果を集約してサマリーを作成
    summary_parts = []
    source_urls = []
    for result in search_results[:5]:  # 上位5件の情報を使用
        summary_parts.append(f"- {result.title}: {result.content[:200]}")
        source_urls.append(result.url)

    if summary_parts:
        summary = "\n".join(summary_parts)
        primary_url = source_urls[0] if source_urls else ""
    else:
        summary = f"「{custom_topic}」についての最新情報"
        primary_url = ""

    # カテゴリを推定
    category = "tech"  # デフォルト
    topic_lower = custom_topic.lower()
    if any(kw in topic_lower for kw in ["ai", "llm", "gpt", "claude", "gemini", "機械学習", "生成ai"]):
        category = "ai"
    elif any(kw in topic_lower for kw in ["python", "javascript", "rust", "go", "react", "next"]):
        category = "programming"
    elif any(kw in topic_lower for kw in ["aws", "azure", "gcp", "docker", "kubernetes"]):
        category = "devops"
    elif any(kw in topic_lower for kw in ["セキュリティ", "脆弱性", "security"]):
        category = "security"

    topic = Topic(
        title=custom_topic,
        link=primary_url,
        summary=summary,
        published=datetime.now(timezone.utc),
        source="カスタムトピック",
        category=category,
        language="ja",
        score=100.0,  # カスタムトピックは最優先
    )

    return topic


def create_single_article(
    collector: TopicCollector,
    generator: ArticleGenerator,
    publisher: NotePublisher,
    tracker: PostedTracker,
    notifier: DiscordNotifier,
    price: int,
    dry_run: bool,
    article_num: int = 1,
    total: int = 1,
    is_free: bool = False,
    thumbnail_generator: ThumbnailGenerator = None,
    custom_topic: str = None,
    pricing_strategy: PricingStrategy = None,
) -> dict:
    """1つの記事を作成して投稿。結果をdictで返す"""
    prefix = f"[{article_num}/{total}] " if total > 1 else ""
    article_type = "無料記事" if is_free else f"有料記事（{price}円）"
    result = {"success": False, "title": "", "error": None, "is_free": is_free}

    # Step 1: トピック収集
    if custom_topic:
        # カスタムトピックが指定された場合
        print(f"\n{prefix}[Step 1/3] カスタムトピックを処理中: {custom_topic}")
        topic = create_custom_topic(custom_topic)
    else:
        # 通常のトピック収集
        print(f"\n{prefix}[Step 1/3] トピックを収集中...")
        posted_urls = tracker.get_posted_urls()
        topic = collector.select_best_topic(exclude_urls=posted_urls, tracker=tracker)

    if not topic:
        print(f"{prefix}エラー: 未投稿のトピックが見つかりませんでした")
        result["error"] = "未投稿のトピックが見つかりませんでした"
        return result

    print(f"\n{prefix}選択されたトピック:")
    print(f"  タイトル: {topic.title}")
    print(f"  ソース: {topic.source}")
    print(f"  リンク: {topic.link}")

    # Determine article type based on topic characteristics
    detected_article_type = generator.detect_article_type(topic) if hasattr(generator, 'detect_article_type') else "speed_analysis"

    # Dynamic pricing if strategy is available and not already free
    if pricing_strategy and not is_free:
        recommendation = pricing_strategy.get_price_recommendation(
            category=topic.category,
            char_count=3000,  # Estimated, will be updated after generation
            article_type=detected_article_type,
        )
        if recommendation["is_free"]:
            is_free = True
            price = 0
            article_type = "無料記事（動的判定）"
            result["is_free"] = True
        elif recommendation["price"] != price:
            price = recommendation["price"]
            article_type = f"有料記事（{price}円・動的価格）"
        print(f"  価格戦略: {', '.join(recommendation['reasoning'])}")

    # Step 2: 記事生成
    print(f"\n{prefix}[Step 2/3] 記事を生成中...（{article_type}）")
    article = generator.generate(topic, is_free=is_free, article_type=detected_article_type)

    print(f"\n{prefix}生成された記事:")
    print(f"  タイトル: {article.title}")
    print(f"  タグ: {', '.join(article.tags) if article.tags else 'なし'}")
    print(f"  文字数: {len(article.content)} 文字")
    print(f"  記事タイプ: {article_type}")
    if article.thumbnail_prompt:
        print(f"  サムネイル: {article.thumbnail_prompt[:50]}...")

    # Recalculate price with actual character count
    if pricing_strategy and not is_free:
        final_recommendation = pricing_strategy.get_price_recommendation(
            category=topic.category,
            char_count=len(article.content),
            article_type=detected_article_type,
        )
        if not final_recommendation["is_free"] and final_recommendation["price"] != price:
            price = final_recommendation["price"]
            article_type = f"有料記事（{price}円・動的価格）"
            print(f"  価格再計算（実文字数）: {price}円")

    # Quality gate: validate article before proceeding
    passed, issues = validate_article_quality(article, is_free)
    if not passed:
        print(f"\n{prefix}品質ゲート: 不合格")
        for issue in issues:
            print(f"  - {issue}")
        result["error"] = f"品質チェック不合格: {'; '.join(issues)}"
        if notifier:
            notifier.send_notification(
                article_title=article.title,
                success=False,
                details=f"品質チェック不合格:\n" + "\n".join(f"- {i}" for i in issues)
            )
        return result
    print(f"  品質ゲート: 合格")

    # サムネイル画像を生成
    thumbnail_path = None
    if thumbnail_generator:
        print(f"\n{prefix}サムネイル画像を生成中...")
        try:
            # thumbnail_promptがあればそれを使用、なければタイトルから生成
            if article.thumbnail_prompt:
                thumbnail_path = thumbnail_generator.generate(article.thumbnail_prompt)
            else:
                thumbnail_path = thumbnail_generator.generate_from_article(
                    article.title, article.tags
                )
            if thumbnail_path:
                print(f"  サムネイル生成完了: {thumbnail_path}")
        except Exception as e:
            print(f"  サムネイル生成エラー（続行します）: {e}")

    # 生成された記事をファイルに保存（バックアップ）
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"article_{timestamp}.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# {article.title}\n\n")
        if article.tags:
            f.write(f"**Tags:** {', '.join(article.tags)}\n\n")
        f.write(f"---\n\n")
        f.write(article.content)
        if article.thumbnail_prompt:
            f.write(f"\n\n---\n\n")
            f.write(f"## Thumbnail Prompt (for Whisk)\n")
            f.write(f"```\n{article.thumbnail_prompt}\n```\n")

    print(f"  バックアップ: {output_file}")

    result["title"] = article.title

    # Dry-runモードの場合はここで終了
    if dry_run:
        print(f"\n{prefix}[Dry-run] noteへの投稿をスキップしました")
        # 投稿済みとして記録（dry-runでも重複防止のため）
        tracker.mark_as_posted(
            topic.link, topic.title,
            category=topic.category,
            tags=article.tags,
            is_free=is_free,
            price=price,
            char_count=len(article.content),
            article_type=detected_article_type,
        )
        result["success"] = True
        if notifier:
            notifier.send_notification(
                article_title=article.title,
                success=True,
                details="Dry-runモードで実行しました。記事は投稿されていません。"
            )
        return result

    # Step 3: noteに投稿
    print(f"\n{prefix}[Step 3/3] noteに投稿中...（価格: {price}円）")
    note_url = publisher.publish(article, thumbnail_path=thumbnail_path, price=price)

    if note_url:
        # 投稿済みとして記録
        tracker.mark_as_posted(
            topic.link, topic.title,
            category=topic.category,
            tags=article.tags,
            is_free=is_free,
            price=price,
            char_count=len(article.content),
            note_url=note_url,
            article_type=detected_article_type,
        )
        print(f"\n{prefix}投稿成功！")
        result["success"] = True
        result["note_url"] = note_url
        if notifier:
            notifier.send_notification(
                article_title=article.title,
                article_url=note_url,
                success=True,
                details=f"タグ: {', '.join(article.tags) if article.tags else 'なし'}\n文字数: {len(article.content)}文字"
            )
        return result
    else:
        print(f"\n{prefix}エラー: noteへの投稿に失敗しました")
        print(f"生成された記事は {output_file} に保存されています")
        result["error"] = "noteへの投稿に失敗しました"
        if notifier:
            notifier.send_notification(
                article_title=article.title,
                success=False,
                details=f"記事は {output_file} に保存されています。"
            )
        return result


def post_existing_article(article_file: str, thumbnail_path: str = None, headless: bool = False, price: int = 300):
    """既存の記事ファイルを投稿する"""
    from src.article_generator import Article

    print("=" * 50)
    print("既存記事の投稿")
    print("=" * 50)

    # 記事ファイルを読み込み
    with open(article_file, "r", encoding="utf-8") as f:
        content = f.read()

    # タイトルとコンテンツを解析
    lines = content.split("\n")
    title = ""
    tags = []
    body_start = 0

    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("**Tags:**"):
            tag_str = line.replace("**Tags:**", "").strip()
            tags = [t.strip() for t in tag_str.split(",")]
        elif line.startswith("---"):
            body_start = i + 1
            break

    body = "\n".join(lines[body_start:]).strip()

    # Articleオブジェクトを作成
    article = Article(
        title=title,
        content=body,
        tags=tags
    )

    print(f"タイトル: {article.title}")
    print(f"タグ: {', '.join(article.tags) if article.tags else 'なし'}")
    print(f"文字数: {len(article.content)} 文字")
    if thumbnail_path:
        print(f"サムネイル: {thumbnail_path}")

    # 投稿
    publisher = NotePublisher(headless=headless, price=price)
    note_url = publisher.publish(article, thumbnail_path=thumbnail_path)

    if note_url:
        print(f"\n投稿成功！ URL: {note_url}")
        return True
    else:
        print("\n投稿失敗")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="AI/プログラミング関連ニュースから記事を自動生成してnoteに投稿"
    )

    # サブコマンドを追加
    subparsers = parser.add_subparsers(dest="command", help="コマンド")

    # postサブコマンド（既存記事の投稿）
    post_parser = subparsers.add_parser("post", help="既存の記事ファイルを投稿")
    post_parser.add_argument(
        "--file",
        required=True,
        help="投稿する記事ファイル（Markdown）"
    )
    post_parser.add_argument(
        "--thumbnail",
        help="サムネイル画像のパス"
    )
    post_parser.add_argument(
        "--headless",
        action="store_true",
        help="ブラウザを非表示で実行"
    )
    post_parser.add_argument(
        "--price",
        type=int,
        default=300,
        help="有料記事の価格（円）。デフォルト: 300円"
    )

    # メインコマンドの引数
    parser.add_argument(
        "--model",
        choices=["opus", "sonnet", "haiku"],
        default=None,
        help="使用するモデル (opus: 最高品質, sonnet: バランス, haiku: 高速・低コスト)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="ブラウザを非表示で実行"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="記事生成まで行い、noteへの投稿はスキップ"
    )
    parser.add_argument(
        "--test-login",
        action="store_true",
        help="noteへのログインのみをテスト"
    )
    parser.add_argument(
        "--price",
        type=int,
        default=300,
        help="有料記事の価格（円）。デフォルト: 300円"
    )
    parser.add_argument(
        "--no-web-search",
        action="store_true",
        help="Web検索を無効にし、RSSフィードのみ使用"
    )
    parser.add_argument(
        "--custom-topic",
        type=str,
        default=os.getenv("CUSTOM_TOPIC", ""),
        help="カスタムトピック（指定するとこの内容でWeb検索して記事を作成）。環境変数CUSTOM_TOPICでも指定可能"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="作成する記事の数（デフォルト: 1）"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="複数記事作成時の間隔（秒）。デフォルト: 60秒"
    )
    parser.add_argument(
        "--free-ratio",
        type=float,
        default=0.0,
        help="無料記事の割合（0.0〜1.0）。例: 0.3 = 30%%の確率で無料記事。デフォルト: 0.0（全て有料）"
    )
    parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        help="サムネイル画像の自動生成を無効化"
    )
    parser.add_argument(
        "--thumbnail-model",
        choices=["flash", "pro"],
        default="pro",
        help="サムネイル生成に使用するモデル (flash: 高速, pro: 高品質)。デフォルト: pro"
    )

    args = parser.parse_args()

    # postサブコマンドの処理
    if args.command == "post":
        success = post_existing_article(
            article_file=args.file,
            thumbnail_path=args.thumbnail,
            headless=args.headless,
            price=args.price
        )
        # クリーンアップ
        cleanup_generated_files()
        sys.exit(0 if success else 1)

    # ログインテストモード
    if args.test_login:
        print("=" * 50)
        print("noteログインテスト")
        print("=" * 50)
        publisher = NotePublisher(headless=False)
        if publisher.test_login():
            print("テスト成功")
        else:
            print("テスト失敗")
        return

    print("=" * 50)
    print("note自動記事作成ツール")
    print("=" * 50)

    # 投稿済みトラッカーを初期化
    tracker = PostedTracker()
    posted_count = tracker.get_posted_count()
    if posted_count > 0:
        print(f"（投稿済み: {posted_count}件）")

    # カスタムトピックの処理（空文字列をNoneに変換）
    custom_topic = args.custom_topic.strip() if args.custom_topic else None
    if custom_topic == "":
        custom_topic = None

    # カスタムトピックモードの表示
    if custom_topic:
        print(f"\n【カスタムトピックモード】")
        print(f"  トピック: {custom_topic}")
        print(f"  ※指定されたトピックについてWeb検索し、記事を作成します")
        # カスタムトピックの場合は1記事のみに制限（同じ内容の記事を複数作る意味がない）
        if args.count > 1:
            print(f"  ※カスタムトピック指定時は1記事のみ作成します")
            args.count = 1

    if args.count > 1:
        print(f"\n{args.count}件の記事を作成します（間隔: {args.interval}秒）")

    if args.free_ratio > 0:
        print(f"無料記事の割合: {args.free_ratio * 100:.0f}%")

    # コレクター、ジェネレーター、通知を初期化
    use_web_search = not args.no_web_search
    collector = TopicCollector(use_web_search=use_web_search)
    generator = ArticleGenerator(model=args.model)
    notifier = DiscordNotifier()

    # サムネイルジェネレーターを初期化（オプション）
    thumbnail_generator = None
    if not args.no_thumbnail:
        try:
            thumbnail_generator = ThumbnailGenerator(model=args.thumbnail_model)
            print(f"サムネイル生成: 有効（{args.thumbnail_model}モデル）")
        except ValueError as e:
            print(f"サムネイル生成: 無効（{e}）")
            thumbnail_generator = None

    # 価格戦略を初期化
    pricing_strategy = PricingStrategy()
    print(f"価格戦略: 有効（データ信頼度: {pricing_strategy.analyzer.confidence:.0%}）")

    # パブリッシャーは有料用と無料用で分けて作成（dry-runでない場合）
    publisher_paid = NotePublisher(headless=args.headless, price=args.price) if not args.dry_run else None
    publisher_free = NotePublisher(headless=args.headless, price=0) if not args.dry_run else None

    # 記事を作成
    success_count = 0
    fail_count = 0
    article_results = []

    for i in range(args.count):
        if i > 0:
            print(f"\n--- 次の記事まで {args.interval}秒 待機中... ---")
            time.sleep(args.interval)

        # ランダムに無料/有料を決定
        is_free = random.random() < args.free_ratio
        publisher = publisher_free if is_free else publisher_paid
        current_price = 0 if is_free else args.price

        result = create_single_article(
            collector=collector,
            generator=generator,
            publisher=publisher,
            tracker=tracker,
            notifier=notifier,
            price=current_price,
            dry_run=args.dry_run,
            article_num=i + 1,
            total=args.count,
            is_free=is_free,
            thumbnail_generator=thumbnail_generator,
            custom_topic=custom_topic,
            pricing_strategy=pricing_strategy,
        )

        article_results.append(result)
        if result["success"]:
            success_count += 1
        else:
            fail_count += 1

    # 結果サマリー
    print("\n" + "=" * 50)
    if args.count > 1:
        print(f"完了！ 成功: {success_count}件, 失敗: {fail_count}件")
        # 日次サマリーメール送信
        if notifier.enabled:
            notifier.send_daily_summary(
                success_count=success_count,
                fail_count=fail_count,
                articles=article_results
            )
    else:
        if success_count > 0:
            print("完了！記事が投稿されました。")
        else:
            print("記事の投稿に失敗しました。")
    print("=" * 50)

    # 生成されたファイルをクリーンアップ（リポジトリを軽く保つため）
    cleanup_generated_files()

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
