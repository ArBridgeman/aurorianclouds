import base64
import json
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from omegaconf import DictConfig
from structlog import get_logger

# If modifying these scopes, must delete credentials
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


@dataclass()
class GmailHelper:
    config: DictConfig
    # client key for desktop created in Google Console for sous_chef project
    client_file_path: Path = None
    # created after first time authorizing user with scope
    auth_file_path: Path = None
    # user created json with recipient & send
    address_book: dict = None

    def __post_init__(self):
        self.client_file_path = self._create_path(self.config.client_file_path)
        self.auth_file_path = self._create_path(self.config.auth_file_path)
        self.address_book = self._load_address_book()

    def send_dataframe_in_email(self, subject: str, dataframe: pd.DataFrame):
        message = self._create_message_basic(subject)
        html = self._format_dataframe_to_html(dataframe)
        message.attach(MIMEText(html, "html"))
        self._send_email({"raw": self._decode_message_byte_str(message)})

    def _connect_service(self) -> Resource:
        credentials = self._load_credentials()
        credentials = self._validate_credentials(credentials)
        # TODO Handle errors from gmail API.
        return build(
            "gmail", "v1", credentials=credentials, cache_discovery=False
        )

    def _create_message_basic(self, subject: str) -> MIMEMultipart:
        message = MIMEMultipart()
        message["to"] = ", ".join(self.address_book["recipient"])
        message["from"] = self.address_book["sender"]
        message["subject"] = subject
        return message

    @staticmethod
    def _create_path(relative_path: str) -> Path:
        # TODO generalize as util across code?
        return Path(ABS_FILE_PATH, relative_path)

    @staticmethod
    def _decode_message_byte_str(message: MIMEMultipart) -> str:
        b64_bytes = base64.urlsafe_b64encode(message.as_bytes())
        return b64_bytes.decode()

    @staticmethod
    def _format_dataframe_to_html(dataframe: pd.DataFrame) -> str:
        return """\
        <html>
          <head></head>
          <body>
            {0}
          </body>
        </html>
        """.format(
            dataframe.to_html()
        )

    def _get_credentials(self) -> Credentials:
        flow = InstalledAppFlow.from_client_secrets_file(
            self.client_file_path.as_posix(), SCOPES
        )
        credentials = flow.run_local_server(port=0)
        self._save_credentials(credentials)
        return credentials

    def _load_address_book(self) -> dict:
        address_book_path = self._create_path(self.config.address_file_path)
        with open(address_book_path.as_posix(), "r") as file:
            return json.load(file)

    def _load_credentials(self) -> Credentials:
        if self.auth_file_path.is_file():
            return Credentials.from_authorized_user_file(
                self.auth_file_path.as_posix(), SCOPES
            )
        return self._get_credentials()

    def _save_credentials(self, credentials: Credentials):
        # save auth_token for future runs
        with open(self.auth_file_path.as_posix(), "w") as auth_token:
            auth_token.write(credentials.to_json())

    def _send_email(self, message: dict[str]):
        service = self._connect_service()

        # TODO handle error when sending message
        message = (
            service.users()
            .messages()
            .send(userId=self.address_book["sender"], body=message)
            .execute()
        )

        FILE_LOGGER.info(
            "[send email]",
            action="email successful sent",
            message_id=message["id"],
        )

    def _validate_credentials(self, credentials: Credentials) -> Credentials:
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self._save_credentials(credentials)
            else:
                return self._get_credentials()
        return credentials
