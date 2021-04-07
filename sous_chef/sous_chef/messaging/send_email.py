import base64
import codecs
import mimetypes
import pickle
from dataclasses import dataclass, field
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from json2html import json2html

# If modifying these scopes, must delete token.pickle.
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


@dataclass
class EmailSender:
    config: dict
    sender: str = field(init=False)
    recipient: str = field(init=False)
    service: Any = field(init=False)
    base_email: str = field(init=False)

    def __post_init__(self):
        self.sender = self.config.sender
        self.recipient = self.config.recipient
        self.service = self.connect_service()

        with codecs.open(Path(self.config.template_path, self.config.email)) as f:
            self.base_email = f.read()

    @staticmethod
    def connect_service():
        credentials = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if Path("token.pickle").exists():
            with open("token.pickle", "rb") as token:
                credentials = pickle.load(token)
        # If no (valid) credentials are available, let the user log in.
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                credentials = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.pickle", "wb") as token:
                pickle.dump(credentials, token)

        return build("gmail", "v1", credentials=credentials)

    @staticmethod
    def decode_message_byte_str(message):
        b64_bytes = base64.urlsafe_b64encode(message.as_bytes())
        return b64_bytes.decode()

    def create_message_with_text(self, subject, message_text):
        message = MIMEText(message_text)
        message["to"] = self.recipient
        message["from"] = self.sender
        message["subject"] = subject
        return {"raw": self.decode_message_byte_str(message)}

    @staticmethod
    def create_html_table_from_json(plan_json):
        return json2html.convert(plan_json)

    def create_message_with_json(self, subject, plan_json, filepath):
        message = MIMEMultipart()
        message["to"] = self.recipient
        message["from"] = self.sender
        message["subject"] = subject

        msg = MIMEText(self.base_email, "html")
        message.attach(msg)

        msg = MIMEText(self.create_html_table_from_json(plan_json), "html")
        message.attach(msg)

        content_type, encoding = mimetypes.guess_type(filepath)
        if content_type is None or encoding is not None:
            content_type = "application/octet-stream"
        main_type, sub_type = content_type.split("/", 1)

        with open(filepath, "r") as f:
            msg = MIMEBase(main_type, sub_type)
            msg.set_payload(f.read())

        filename = Path(filepath).name
        msg.add_header("Content-Disposition", "attachment", filename=filename)
        message.attach(msg)
        return {"raw": self.decode_message_byte_str(message)}

    def send_message(self, message):
        try:
            message = (
                self.service.users()
                .messages()
                .send(userId=self.sender, body=message)
                .execute()
            )
            print("Message Id: %s" % message["id"])
            return message
        except Exception as error:
            print("An error occurred: %s" % error)

    def send_message_with_text(self, subject, message_text):
        message = self.create_message_with_text(subject, message_text)
        self.send_message(message)

    def send_message_with_attachment(self, subject, message_text, file):
        message = self.create_message_with_json(subject, message_text, file)
        self.send_message(message)
