import pytest
from scraper.filter_verifier import FilterVerifier


class TestFilterVerifier:
    def test_extract_filter_giftcardmall(self):
        text = "Filters: GiftCardMall\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.extract_filter(text) == "GiftCardMall"

    def test_extract_filter_none(self):
        text = "Filters: None\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.extract_filter(text) == "None"

    def test_extract_filter_missing(self):
        text = "Page 1/3\nUpdated: 15:06"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.extract_filter(text) is None

    def test_is_correct_filter_true(self):
        text = "Filters: GiftCardMall\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.is_correct_filter(text) is True

    def test_is_correct_filter_false(self):
        text = "Filters: None\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.is_correct_filter(text) is False

    def test_is_correct_filter_missing_line(self):
        text = "Page 1/3\nUpdated: 15:06"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.is_correct_filter(text) is False

    def test_case_insensitive(self):
        text = "Filters: giftcardmall\nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.is_correct_filter(text) is True

    def test_whitespace_handling(self):
        text = "Filters:   GiftCardMall  \nPage 1/3"
        verifier = FilterVerifier("GiftCardMall")
        assert verifier.extract_filter(text) == "GiftCardMall"
