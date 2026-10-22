"""Unit tests for in-memory RateLimiter."""
import time
import pytest
from app.middleware.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for in-memory RateLimiter."""

    def setup_method(self):
        self.rl = RateLimiter()

    def test_allows_within_limit(self):
        """Requests within limit are allowed."""
        assert self.rl.check_rate("test:key", 5, 60) is True
        assert self.rl.check_rate("test:key", 5, 60) is True

    def test_blocks_over_limit(self):
        """Requests over limit are blocked."""
        for _ in range(5):
            self.rl.check_rate("test:block", 5, 60)
        assert self.rl.check_rate("test:block", 5, 60) is False

    def test_different_keys_independent(self):
        """Different keys have independent limits."""
        for _ in range(5):
            self.rl.check_rate("key:a", 5, 60)
        assert self.rl.check_rate("key:b", 5, 60) is True

    def test_record_failed_login(self):
        """Failed login tracking works."""
        count = self.rl.record_failed_login("192.168.1.1")
        assert count == 1
        count = self.rl.record_failed_login("192.168.1.1")
        assert count == 2

    def test_is_blocked_after_threshold(self):
        """IP blocked after max_fails threshold."""
        for _ in range(10):
            self.rl.record_failed_login("10.0.0.1")
        assert self.rl.is_blocked("10.0.0.1", max_fails=10) is True

    def test_not_blocked_below_threshold(self):
        """IP not blocked below threshold."""
        for _ in range(5):
            self.rl.record_failed_login("10.0.0.2")
        assert self.rl.is_blocked("10.0.0.2", max_fails=10) is False

    def test_different_ips_independent(self):
        """Different IPs tracked independently."""
        for _ in range(10):
            self.rl.record_failed_login("1.1.1.1")
        assert self.rl.is_blocked("1.1.1.1", max_fails=10) is True
        assert self.rl.is_blocked("2.2.2.2", max_fails=10) is False
