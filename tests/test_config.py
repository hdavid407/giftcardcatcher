import pytest
from scraper.config import ScraperConfig


class TestScraperConfigFilterVerification:
    @pytest.fixture(autouse=True)
    def setup_required_env(self, monkeypatch):
        """Provide required env vars so ScraperConfig can instantiate."""
        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "test_hash")
        monkeypatch.setenv("TELEGRAM_PHONE", "+1234567890")
        monkeypatch.setenv("TARGET_BOT_USERNAME", "@testbot")

    def test_filter_verification_enabled_defaults_to_true(self, monkeypatch):
        monkeypatch.delenv("FILTER_VERIFICATION_ENABLED", raising=False)
        config = ScraperConfig()
        assert config.filter_verification_enabled is True

    def test_filter_verification_retries_defaults_to_three(self, monkeypatch):
        monkeypatch.delenv("FILTER_VERIFICATION_RETRIES", raising=False)
        config = ScraperConfig()
        assert config.filter_verification_retries == 3

    def test_filter_verification_enabled_parses_true(self, monkeypatch):
        monkeypatch.setenv("FILTER_VERIFICATION_ENABLED", "true")
        config = ScraperConfig()
        assert config.filter_verification_enabled is True

    def test_filter_verification_enabled_parses_false(self, monkeypatch):
        monkeypatch.setenv("FILTER_VERIFICATION_ENABLED", "false")
        config = ScraperConfig()
        assert config.filter_verification_enabled is False

    def test_filter_verification_enabled_parses_mixed_case_true(self, monkeypatch):
        monkeypatch.setenv("FILTER_VERIFICATION_ENABLED", "True")
        config = ScraperConfig()
        assert config.filter_verification_enabled is True

    def test_filter_verification_enabled_parses_uppercase_true(self, monkeypatch):
        monkeypatch.setenv("FILTER_VERIFICATION_ENABLED", "TRUE")
        config = ScraperConfig()
        assert config.filter_verification_enabled is True

    def test_filter_verification_enabled_parses_uppercase_false(self, monkeypatch):
        monkeypatch.setenv("FILTER_VERIFICATION_ENABLED", "FALSE")
        config = ScraperConfig()
        assert config.filter_verification_enabled is False

    def test_filter_verification_enabled_parses_non_true_as_false(self, monkeypatch):
        monkeypatch.setenv("FILTER_VERIFICATION_ENABLED", "0")
        config = ScraperConfig()
        assert config.filter_verification_enabled is False

    def test_filter_verification_retries_parses_integer(self, monkeypatch):
        monkeypatch.setenv("FILTER_VERIFICATION_RETRIES", "5")
        config = ScraperConfig()
        assert config.filter_verification_retries == 5

    def test_filter_verification_retries_parses_zero(self, monkeypatch):
        monkeypatch.setenv("FILTER_VERIFICATION_RETRIES", "0")
        config = ScraperConfig()
        assert config.filter_verification_retries == 0
