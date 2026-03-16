"""noteスタッツスクレイピングモジュール - 記事パフォーマンスデータの収集"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.note_auth import create_browser_context, setup_page, login


STATS_URL = "https://note.com/sitesettings/stats"
DATA_DIR = Path("data")
STATS_FILE = DATA_DIR / "article_stats.json"


def _load_existing_stats() -> dict:
    """Load existing stats data"""
    if STATS_FILE.exists():
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_updated": None, "articles": []}


def _save_stats(stats: dict) -> None:
    """Save stats data"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def _load_posted_topics() -> list[dict]:
    """Load posted topics for title matching"""
    posted_file = DATA_DIR / "posted_topics.json"
    if posted_file.exists():
        with open(posted_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("topics", [])
    return []


def _match_with_posted_topics(scraped_title: str, posted_topics: list[dict]) -> dict | None:
    """Match scraped article title with posted topics"""
    scraped_normalized = re.sub(r'[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', '', scraped_title.lower())

    best_match = None
    best_similarity = 0.0

    for topic in posted_topics:
        posted_title = topic.get("title", "")
        posted_normalized = re.sub(r'[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', '', posted_title.lower())

        if not scraped_normalized or not posted_normalized:
            continue

        shorter = scraped_normalized if len(scraped_normalized) <= len(posted_normalized) else posted_normalized
        longer = posted_normalized if len(scraped_normalized) <= len(posted_normalized) else scraped_normalized

        common_chars = sum(1 for c in shorter if c in longer)
        similarity = common_chars / len(shorter) if shorter else 0.0

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = topic

    if best_similarity >= 0.5:
        return best_match
    return None


def scrape_stats(page: Page) -> list[dict]:
    """Scrape article stats from note.com stats page

    Args:
        page: Logged-in Playwright page

    Returns:
        List of article stat dicts
    """
    print("スタッツページに移動中...")
    page.goto(STATS_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(3)

    page.screenshot(path="debug_stats_page.png")
    print("  デバッグ: スタッツページのスクリーンショットを保存")

    # Check if redirected to login
    if "login" in page.url.lower():
        print("  エラー: ログインページにリダイレクトされました")
        return []

    articles = []

    # Scroll to load all articles and collect stats
    # note.com stats page shows a table/list of articles with PV, likes, etc.
    try:
        # Wait for stats content to load
        page.wait_for_selector('[class*="stats"], [class*="Stats"], table, [class*="article"]', timeout=15000)
        time.sleep(2)

        # Try multiple approaches to find article stats
        # Approach 1: Table rows
        stats_data = page.evaluate("""() => {
            const articles = [];

            // Look for table rows with article data
            const rows = document.querySelectorAll('tr, [class*="row"], [class*="Row"], [class*="item"], [class*="Item"]');
            for (const row of rows) {
                const titleEl = row.querySelector('a, [class*="title"], [class*="Title"]');
                if (!titleEl) continue;

                const title = titleEl.textContent.trim();
                if (!title || title.length < 5) continue;

                const link = titleEl.href || '';

                // Find numeric values (PV, likes, etc.)
                const numbers = [];
                const cells = row.querySelectorAll('td, [class*="cell"], [class*="Cell"], [class*="count"], [class*="Count"], [class*="num"], [class*="Num"]');
                for (const cell of cells) {
                    const text = cell.textContent.trim().replace(/,/g, '');
                    const num = parseInt(text, 10);
                    if (!isNaN(num)) {
                        numbers.push(num);
                    }
                }

                if (title) {
                    articles.push({
                        title: title,
                        note_url: link,
                        numbers: numbers
                    });
                }
            }

            // Approach 2: If no table, look for card-style layouts
            if (articles.length === 0) {
                const cards = document.querySelectorAll('[class*="article"], [class*="Article"], [class*="note"], [class*="Note"]');
                for (const card of cards) {
                    const titleEl = card.querySelector('a, h2, h3, [class*="title"], [class*="Title"]');
                    if (!titleEl) continue;

                    const title = titleEl.textContent.trim();
                    if (!title || title.length < 5) continue;

                    const link = (card.querySelector('a') || titleEl).href || '';

                    const numbers = [];
                    const numEls = card.querySelectorAll('[class*="count"], [class*="Count"], [class*="view"], [class*="View"], [class*="like"], [class*="Like"]');
                    for (const el of numEls) {
                        const text = el.textContent.trim().replace(/,/g, '');
                        const num = parseInt(text, 10);
                        if (!isNaN(num)) {
                            numbers.push(num);
                        }
                    }

                    articles.push({
                        title: title,
                        note_url: link,
                        numbers: numbers
                    });
                }
            }

            return articles;
        }""")

        if stats_data:
            print(f"  {len(stats_data)}件の記事データを取得")
            for item in stats_data:
                article_stat = {
                    "title": item["title"],
                    "note_url": item.get("note_url", ""),
                    "views": item["numbers"][0] if len(item["numbers"]) > 0 else 0,
                    "likes": item["numbers"][1] if len(item["numbers"]) > 1 else 0,
                    "purchases": item["numbers"][2] if len(item["numbers"]) > 2 else 0,
                    "revenue": item["numbers"][3] if len(item["numbers"]) > 3 else 0,
                }
                articles.append(article_stat)
        else:
            print("  警告: 記事データが取得できませんでした")
            page.screenshot(path="debug_stats_no_data.png")

            # Scroll down to try loading more content
            for scroll_attempt in range(5):
                page.evaluate("window.scrollBy(0, 500)")
                time.sleep(1)

            page.screenshot(path="debug_stats_after_scroll.png")

            # Try getting page HTML for debugging
            html_preview = page.evaluate("() => document.body.innerText.substring(0, 2000)")
            print(f"  ページ内容プレビュー: {html_preview[:500]}...")

    except Exception as e:
        print(f"  スタッツ取得エラー: {e}")
        page.screenshot(path="error_stats_scrape.png")

    return articles


def run_stats_collection(headless: bool = True) -> dict:
    """Run full stats collection pipeline

    Returns:
        Stats dict with articles data
    """
    print("=" * 50)
    print("noteスタッツ収集")
    print("=" * 50)

    existing_stats = _load_existing_stats()
    posted_topics = _load_posted_topics()

    with sync_playwright() as p:
        browser, context = create_browser_context(p, headless=headless)
        page = setup_page(context)

        try:
            if not login(page):
                print("ログインに失敗しました。スタッツ収集を中止します。")
                return existing_stats

            print("ログイン成功")

            scraped_articles = scrape_stats(page)

            if not scraped_articles:
                print("記事データが取得できませんでした")
                return existing_stats

            # Match with posted topics and merge
            updated_articles = []
            for scraped in scraped_articles:
                matched_topic = _match_with_posted_topics(scraped["title"], posted_topics)

                article_entry = {
                    "title": scraped["title"],
                    "note_url": scraped.get("note_url", ""),
                    "views": scraped.get("views", 0),
                    "likes": scraped.get("likes", 0),
                    "purchases": scraped.get("purchases", 0),
                    "revenue": scraped.get("revenue", 0),
                    "scraped_at": datetime.now().isoformat(),
                }

                if matched_topic:
                    article_entry["source_url"] = matched_topic.get("url", "")
                    article_entry["category"] = matched_topic.get("category", "")
                    article_entry["tags"] = matched_topic.get("tags", [])
                    article_entry["is_free"] = matched_topic.get("is_free", True)
                    article_entry["price"] = matched_topic.get("price", 0)
                    article_entry["posted_at"] = matched_topic.get("posted_at", "")

                updated_articles.append(article_entry)

            # Merge with existing stats (keep history)
            existing_by_title = {a["title"]: a for a in existing_stats.get("articles", [])}
            for article in updated_articles:
                title = article["title"]
                if title in existing_by_title:
                    # Keep history of views/likes
                    old = existing_by_title[title]
                    if "history" not in old:
                        old["history"] = []
                    old["history"].append({
                        "views": old.get("views", 0),
                        "likes": old.get("likes", 0),
                        "purchases": old.get("purchases", 0),
                        "revenue": old.get("revenue", 0),
                        "scraped_at": old.get("scraped_at", ""),
                    })
                    # Limit history to 30 entries
                    old["history"] = old["history"][-30:]
                    # Update current values
                    old.update(article)
                    existing_by_title[title] = old
                else:
                    existing_by_title[title] = article

            stats = {
                "last_updated": datetime.now().isoformat(),
                "articles": list(existing_by_title.values()),
            }

            _save_stats(stats)
            print(f"\nスタッツを保存しました: {STATS_FILE}")
            print(f"  記事数: {len(stats['articles'])}")

            return stats

        except Exception as e:
            print(f"エラーが発生しました: {e}")
            page.screenshot(path="error_stats_collection.png")
            return existing_stats

        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="noteスタッツ収集")
    parser.add_argument("--headless", action="store_true", help="ブラウザを非表示で実行")
    args = parser.parse_args()

    run_stats_collection(headless=args.headless)


if __name__ == "__main__":
    main()
