"""Tests for the Signal landing page HTML content."""

import os
import unittest


class LandingPageTest(unittest.TestCase):
    """Verify the landing page contains required sections."""

    @classmethod
    def setUpClass(cls):
        page_path = os.path.join(os.path.dirname(__file__), "index.html")
        with open(page_path, "r") as f:
            cls.html = f.read()

    def test_has_title(self):
        self.assertIn("TradeStream Signals", self.html)

    def test_has_pricing_section(self):
        self.assertIn('id="pricing"', self.html)

    def test_has_three_tiers(self):
        self.assertIn("Free", self.html)
        self.assertIn("$29", self.html)
        self.assertIn("$99", self.html)

    def test_has_features_section(self):
        self.assertIn('id="features"', self.html)
        self.assertIn("30+ Strategies", self.html)
        self.assertIn("Real-Time Delivery", self.html)

    def test_has_cta_buttons(self):
        self.assertIn("btn-pro", self.html)
        self.assertIn("btn-enterprise", self.html)

    def test_has_performance_stats(self):
        self.assertIn("stat-winrate", self.html)
        self.assertIn("stat-signals", self.html)

    def test_has_how_it_works(self):
        self.assertIn('id="how-it-works"', self.html)

    def test_has_checkout_script(self):
        self.assertIn("/checkout", self.html)
        self.assertIn("startCheckout", self.html)

    def test_has_api_docs_link(self):
        self.assertIn("/docs", self.html)

    def test_meta_viewport(self):
        self.assertIn('name="viewport"', self.html)


if __name__ == "__main__":
    unittest.main()
