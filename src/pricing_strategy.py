"""動的価格設定モジュール - カテゴリ・文字数・記事タイプに応じた価格最適化"""

from .performance_analyzer import PerformanceAnalyzer


# Base prices by category
CATEGORY_BASE_PRICES = {
    "ai": 300,
    "programming": 300,
    "web": 200,
    "devops": 300,
    "security": 300,
    "business": 200,
    "column": 200,
    "tech": 200,
}

# Article type price adjustments
ARTICLE_TYPE_MULTIPLIERS = {
    "speed_analysis": 1.0,    # Speed analysis: standard price
    "comparison": 1.2,        # Comparison: higher value
    "practical_guide": 1.3,   # Tutorial: highest practical value
    "trend_overview": 0.8,    # Trend overview: lower entry price
}

# Character count thresholds for price tiers
CHAR_COUNT_TIERS = [
    (6000, 1.3),   # 6000+ chars: premium
    (4000, 1.1),   # 4000+ chars: standard+
    (2000, 1.0),   # 2000+ chars: standard
    (0, 0.8),      # Under 2000: discount
]


class PricingStrategy:
    """Dynamic pricing based on article characteristics and performance data"""

    MIN_PRICE = 100
    MAX_PRICE = 1000
    DEFAULT_PRICE = 300

    def __init__(self):
        self.analyzer = PerformanceAnalyzer()

    def calculate_price(
        self,
        category: str = "tech",
        char_count: int = 3000,
        article_type: str = "speed_analysis",
    ) -> int:
        """Calculate optimal price for an article

        Args:
            category: Article category
            char_count: Character count of the article
            article_type: Type of article (speed_analysis, comparison, practical_guide, trend_overview)

        Returns:
            Price in yen (rounded to nearest 100)
        """
        # Base price from category
        base_price = CATEGORY_BASE_PRICES.get(category, self.DEFAULT_PRICE)

        # Article type multiplier
        type_mult = ARTICLE_TYPE_MULTIPLIERS.get(article_type, 1.0)

        # Character count multiplier
        char_mult = 1.0
        for threshold, mult in CHAR_COUNT_TIERS:
            if char_count >= threshold:
                char_mult = mult
                break

        # Performance-based adjustment
        perf_mult = self._get_performance_multiplier(category)

        # Calculate final price
        price = base_price * type_mult * char_mult * perf_mult

        # Round to nearest 100, clamp to range
        price = max(self.MIN_PRICE, min(self.MAX_PRICE, round(price / 100) * 100))

        return price

    def _get_performance_multiplier(self, category: str) -> float:
        """Get price multiplier based on actual sales performance"""
        if not self.analyzer.has_sufficient_data:
            return 1.0

        cat_perf = self.analyzer.get_category_performance()
        if category not in cat_perf:
            return 1.0

        cat_data = cat_perf[category]
        avg_purchases = cat_data.get("avg_purchases", 0)

        # If a category sells well, we can price higher
        if avg_purchases >= 3:
            return 1.3
        elif avg_purchases >= 1:
            return 1.1
        elif avg_purchases > 0:
            return 1.0
        else:
            return 0.9

    def should_be_free(self, category: str, article_type: str) -> bool:
        """Recommend whether an article should be free (for audience growth)

        Free articles are strategic - only when performance data supports it.
        trend_overview is NOT unconditionally free (deep analysis has paid value).
        """
        # Only use performance data to decide free/paid
        if self.analyzer.has_sufficient_data:
            cat_perf = self.analyzer.get_category_performance()
            if category in cat_perf:
                avg_purchases = cat_perf[category].get("avg_purchases", 0)
                avg_views = cat_perf[category].get("avg_views", 0)
                # If high views but very low purchases, better as free content
                if avg_views > 100 and avg_purchases < 0.5:
                    return True

        return False

    def get_price_recommendation(
        self,
        category: str,
        char_count: int,
        article_type: str,
    ) -> dict:
        """Get detailed pricing recommendation

        Returns:
            Dict with price, is_free recommendation, and reasoning
        """
        is_free = self.should_be_free(category, article_type)
        price = 0 if is_free else self.calculate_price(category, char_count, article_type)

        reasoning = []
        if is_free:
            reasoning.append("このカテゴリはPVは高いが購入率が低いため無料推奨")
        else:
            reasoning.append(f"カテゴリ基本価格: {CATEGORY_BASE_PRICES.get(category, self.DEFAULT_PRICE)}円")
            type_mult = ARTICLE_TYPE_MULTIPLIERS.get(article_type, 1.0)
            if type_mult != 1.0:
                reasoning.append(f"記事タイプ調整: x{type_mult}")
            if char_count >= 4000:
                reasoning.append(f"文字数ボーナス: {char_count}文字")

        return {
            "price": price,
            "is_free": is_free,
            "reasoning": reasoning,
        }
