import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.messaging.gmail_api import GmailHelper


@pytest.fixture
def gmail_helper():
    with initialize(version_base=None, config_path="../../../config/messaging"):
        config = compose(config_name="gmail_api")
        return GmailHelper(config.gmail)


DEFAULT_SUBJECT = "[sous_chef_tests]"


@pytest.mark.gmail
class TestGmailHelper:
    @staticmethod
    @pytest.mark.skip(reason="need to frequently update credentials")
    def test_send_dataframe_in_email(gmail_helper):
        fake_df = pd.DataFrame({"Vars": ["a", "b"], "Vals": [1.1, 2.4]})
        gmail_helper.send_dataframe_in_email(DEFAULT_SUBJECT, fake_df)
