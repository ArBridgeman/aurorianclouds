import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.messaging.gmail_api import GmailHelper

DEFAULT_TEST_RECIPIENT = "test_recipient"
DEFAULT_TEST_SENDER = "test_sender"


@pytest.fixture
def gmail_helper():
    with initialize(config_path="../../../config/messaging"):
        config = compose(config_name="gmail_api")
        gmail_helper = GmailHelper(config.gmail)
        gmail_helper.address_book = {
            "recipient": [DEFAULT_TEST_RECIPIENT],
            "sender": DEFAULT_TEST_SENDER,
        }
        return gmail_helper


class TestGmailHelper:
    @staticmethod
    def test__create_message_basic(gmail_helper):
        subject = "test"
        result = gmail_helper._create_message_basic(subject)
        assert result["to"] == DEFAULT_TEST_RECIPIENT
        assert result["from"] == DEFAULT_TEST_SENDER
        assert result["subject"] == subject

    @staticmethod
    def test__create_path(gmail_helper):
        assert gmail_helper._create_path("../test/path").parts[-6:] == (
            "sous_chef",
            "sous_chef",
            "messaging",
            "..",
            "test",
            "path",
        )

    @staticmethod
    def test__decode_message_byte_str(gmail_helper):
        message = gmail_helper._create_message_basic("test")
        # difficult to test further, as each time different values
        gmail_helper._decode_message_byte_str(message)

    @staticmethod
    def test__format_dataframe_to_html(gmail_helper):
        fake_df = pd.DataFrame({"Vars": ["a", "b"], "Vals": [1.1, 2.4]})
        # testing html str is messy
        gmail_helper._format_dataframe_to_html(fake_df)
