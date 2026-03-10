"""Tests for the Signal Dashboard UI."""

import os
import re
import unittest


class SignalDashboardTest(unittest.TestCase):
    """Tests for the Signal Dashboard HTML/JS application."""

    @classmethod
    def setUpClass(cls):
        """Load the HTML file content."""
        html_path = os.path.join(os.path.dirname(__file__), "index.html")
        with open(html_path, "r") as f:
            cls.html_content = f.read()

    # ---- Structure Tests ----

    def test_html_has_doctype(self):
        """HTML file should start with DOCTYPE."""
        self.assertTrue(self.html_content.strip().lower().startswith("<!doctype html>"))

    def test_html_has_title(self):
        """HTML should have a title tag."""
        self.assertIn("<title>", self.html_content)
        self.assertIn("Signal Dashboard", self.html_content)

    def test_html_has_viewport_meta(self):
        """HTML should have viewport meta for responsive design."""
        self.assertIn('name="viewport"', self.html_content)

    # ---- Component Tests ----

    def test_stats_bar_exists(self):
        """Stats bar with connection status should exist."""
        self.assertIn("stats-bar", self.html_content)
        self.assertIn("statusDot", self.html_content)
        self.assertIn("connectionLabel", self.html_content)
        self.assertIn("eventsPerSec", self.html_content)

    def test_filter_panel_exists(self):
        """Filter panel with symbol, score, tier, action filters should exist."""
        self.assertIn("symbolFilter", self.html_content)
        self.assertIn("scoreFilter", self.html_content)
        self.assertIn("data-tier", self.html_content)
        self.assertIn("data-action", self.html_content)

    def test_signal_feed_exists(self):
        """Main signal feed container should exist."""
        self.assertIn("signalFeed", self.html_content)

    def test_empty_state_exists(self):
        """Empty state should be shown when no signals."""
        self.assertIn("emptyState", self.html_content)
        self.assertIn("No signals yet", self.html_content)

    def test_summary_cards_exist(self):
        """HOT/WARM/COLD summary cards should exist."""
        self.assertIn("hotCount", self.html_content)
        self.assertIn("warmCount", self.html_content)
        self.assertIn("coldCount", self.html_content)

    # ---- SSE Client Tests ----

    def test_event_source_usage(self):
        """JavaScript should use EventSource for SSE connection."""
        self.assertIn("EventSource", self.html_content)
        self.assertIn("new EventSource", self.html_content)

    def test_sse_event_listeners(self):
        """SSE client should listen for signal, reasoning, tool_call events."""
        self.assertIn('addEventListener("signal"', self.html_content)
        self.assertIn('addEventListener("reasoning"', self.html_content)
        self.assertIn('addEventListener("tool_call"', self.html_content)
        self.assertIn('addEventListener("heartbeat"', self.html_content)

    def test_last_event_id_tracking(self):
        """SSE client should track lastEventId for reconnection."""
        self.assertIn("lastEventId", self.html_content)

    def test_reconnection_handling(self):
        """SSE client should handle reconnection states."""
        self.assertIn("CONNECTING", self.html_content)
        self.assertIn("CLOSED", self.html_content)

    def test_json_parsing(self):
        """SSE event data should be parsed as JSON."""
        self.assertIn("JSON.parse", self.html_content)

    # ---- Filter Logic Tests ----

    def test_tier_filter_options(self):
        """Tier filter should have HOT, WARM, COLD options."""
        self.assertIn('data-tier="HOT"', self.html_content)
        self.assertIn('data-tier="WARM"', self.html_content)
        self.assertIn('data-tier="COLD"', self.html_content)

    def test_action_filter_options(self):
        """Action filter should have BUY, SELL, HOLD options."""
        self.assertIn('data-action="BUY"', self.html_content)
        self.assertIn('data-action="SELL"', self.html_content)
        self.assertIn('data-action="HOLD"', self.html_content)

    def test_event_type_filter(self):
        """Event type filter should exist for signal, reasoning, tool_call."""
        self.assertIn('data-event="signal"', self.html_content)
        self.assertIn('data-event="reasoning"', self.html_content)
        self.assertIn('data-event="tool_call"', self.html_content)

    def test_symbol_filter_input(self):
        """Symbol filter input should exist with placeholder."""
        self.assertIn('id="symbolFilter"', self.html_content)
        self.assertIn("BTC-USD", self.html_content)

    def test_score_filter_range(self):
        """Score filter should be a range slider from 0-100."""
        self.assertIn('id="scoreFilter"', self.html_content)
        self.assertIn('min="0"', self.html_content)
        self.assertIn('max="100"', self.html_content)

    # ---- Visual Design Tests ----

    def test_dark_theme(self):
        """Dashboard should use a dark theme."""
        # Check for dark background colors
        self.assertIn("#0a0e17", self.html_content)
        self.assertIn("#111827", self.html_content)

    def test_tier_color_coding(self):
        """Tiers should be color-coded: HOT=red, WARM=yellow, COLD=blue."""
        self.assertIn("tier-hot", self.html_content)
        self.assertIn("tier-warm", self.html_content)
        self.assertIn("tier-cold", self.html_content)

    def test_action_color_coding(self):
        """Actions should be color-coded: BUY=green, SELL=red, HOLD=yellow."""
        self.assertIn("action-buy", self.html_content)
        self.assertIn("action-sell", self.html_content)
        self.assertIn("action-hold", self.html_content)

    def test_monospace_font(self):
        """Dashboard should use monospace font family."""
        self.assertIn("monospace", self.html_content)

    # ---- Signal Card Rendering Tests ----

    def test_signal_card_elements(self):
        """Signal cards should render tier, symbol, action, confidence, score."""
        self.assertIn("tier-badge", self.html_content)
        self.assertIn("signal-symbol", self.html_content)
        self.assertIn("signal-action", self.html_content)
        self.assertIn("signal-confidence", self.html_content)
        self.assertIn("signal-score", self.html_content)

    def test_reasoning_panel(self):
        """Reasoning panel should show steps and tool calls."""
        self.assertIn("reasoning-panel", self.html_content)
        self.assertIn("reasoning-step", self.html_content)
        self.assertIn("tool-call-item", self.html_content)

    def test_latency_badges(self):
        """Tool calls should show latency with fast/medium/slow badges."""
        self.assertIn("latency-badge", self.html_content)
        self.assertIn("fast", self.html_content)
        self.assertIn("medium", self.html_content)
        self.assertIn("slow", self.html_content)

    # ---- Reasoning Expansion Tests ----

    def test_vertical_timeline(self):
        """Reasoning panel should use a vertical timeline layout."""
        self.assertIn("reasoning-timeline", self.html_content)
        self.assertIn("timeline-node", self.html_content)
        self.assertIn("timeline-dot", self.html_content)

    def test_expand_collapse_animation(self):
        """Reasoning panel should animate open/close with max-height transition."""
        self.assertIn("max-height", self.html_content)
        self.assertIn("transition", self.html_content)
        # Panel uses max-height for smooth animation
        self.assertIn("max-height: 0", self.html_content)
        self.assertIn("max-height: 2000px", self.html_content)

    def test_expand_indicator(self):
        """Signal cards should show an expand/collapse indicator."""
        self.assertIn("expand-indicator", self.html_content)

    def test_tool_call_expandable_details(self):
        """Tool calls should have expandable params and results."""
        self.assertIn("tool-details", self.html_content)
        self.assertIn("tool-details-inner", self.html_content)
        self.assertIn("tool-detail-label", self.html_content)
        self.assertIn("tool-detail-content", self.html_content)
        self.assertIn("details-open", self.html_content)

    def test_tool_calls_linked_to_steps(self):
        """Tool calls should be grouped by reasoning step number."""
        self.assertIn("toolsByStep", self.html_content)
        self.assertIn("tc.step", self.html_content)

    def test_reasoning_step_timestamps(self):
        """Reasoning steps should display timestamps."""
        self.assertIn("step-timestamp", self.html_content)
        self.assertIn("step.timestamp", self.html_content)

    def test_latency_thresholds(self):
        """Latency thresholds: <100ms fast, <500ms medium, >=500ms slow."""
        # Check the JS thresholds
        self.assertIn("latency < 100", self.html_content)
        self.assertIn("latency < 500", self.html_content)

    def test_tool_result_badge(self):
        """Tool calls with results should show a result badge."""
        self.assertIn("tool-result-badge", self.html_content)

    def test_tool_call_click_does_not_toggle_card(self):
        """Clicking tool calls should not toggle the signal card."""
        self.assertIn("tool-call-item", self.html_content)
        self.assertIn("stopPropagation", self.html_content)

    def test_reasoning_events_before_signal(self):
        """Reasoning events should be stored even before signal arrives."""
        # The handler should init the map if signal_id not present
        self.assertIn("reasoningSteps.set(signalId, [])", self.html_content)

    # ---- Security Tests ----

    def test_html_escaping(self):
        """Signal data should be HTML-escaped to prevent XSS."""
        self.assertIn("escapeHtml", self.html_content)

    def test_read_only(self):
        """Dashboard should not have any form submission or action triggers."""
        # No form submit, no POST requests, no action buttons
        self.assertNotIn('method="POST"', self.html_content)
        self.assertNotIn(".submit()", self.html_content)
        self.assertNotIn("fetch(", self.html_content)

    # ---- Gateway URL Tests ----

    def test_gateway_url_input(self):
        """Gateway URL should be configurable."""
        self.assertIn("gatewayUrl", self.html_content)
        self.assertIn("/events", self.html_content)

    def test_connect_button(self):
        """Connect/Disconnect button should exist."""
        self.assertIn("connectBtn", self.html_content)

    # ---- Events Per Second Counter ----

    def test_events_per_second(self):
        """Events per second counter should exist."""
        self.assertIn("setInterval", self.html_content)
        self.assertIn("eventTimestamps", self.html_content)


class NginxConfigTest(unittest.TestCase):
    """Tests for the nginx configuration."""

    @classmethod
    def setUpClass(cls):
        """Load the nginx config."""
        config_path = os.path.join(os.path.dirname(__file__), "nginx.conf")
        with open(config_path, "r") as f:
            cls.config = f.read()

    def test_listens_on_8080(self):
        """Nginx should listen on port 8080."""
        self.assertIn("listen 8080", self.config)

    def test_serves_index_html(self):
        """Nginx should serve index.html."""
        self.assertIn("index.html", self.config)

    def test_sse_proxy(self):
        """Nginx should proxy /events to agent gateway."""
        self.assertIn("location /events", self.config)
        self.assertIn("proxy_pass", self.config)
        self.assertIn("proxy_buffering off", self.config)

    def test_no_buffering_for_sse(self):
        """SSE proxy should disable buffering and caching."""
        self.assertIn("proxy_buffering off", self.config)
        self.assertIn("proxy_cache off", self.config)
        self.assertIn("chunked_transfer_encoding off", self.config)

    def test_health_check(self):
        """Health check endpoint should exist."""
        self.assertIn("/healthz", self.config)


if __name__ == "__main__":
    unittest.main()
