import base64
import logging
from dataclasses import dataclass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# xin quyền đọc + đánh dấu đã đọc/ gán nhãn, k cân quyền gửi mail

SCOPE = ["https://www.googleapis.com/auth/gmail.modify"]


@dataclass
class EmailAttachment:
    filename: str
    data: bytes
    mime_type: str


@dataclass
class EmailMessage:
    message_id: str
    sender: str
    subject: str
    attachments: list[EmailAttachment]


class GmailClient:
    def __init__(self):
        self.service = build("gmail", "v1", credentials=self._load_credentials())

        profile = self.service.users().getProfile(userId="me").execute()
        logger.info("Gmail api đang xác thực với tài khoản: %s", profile["emailAddress"])

    def _load_credentials(self) -> Credentials:
        creds = None
        token_path = settings.GMAIL_TOKEN_PATH

        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPE)
        except FileNotFoundError:
            creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.GMAIL_CREDENTIALS_PATH, SCOPE
                )
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as f:
                f.write(creds.to_json())
        return creds

    def list_new_messages(self, max_results: int = 20) -> list[str]:
        query = settings.GMAIL_POLL_QUERY
        result = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = result.get("messages", [])
        return [m["id"] for m in messages]

    def fetch_message_with_attachments(self, message_id: str) -> EmailMessage:
        msg = (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        sender = headers.get("From", "")
        subject = headers.get("Subject", "")

        attachments = self._extract_attachments(message_id, msg["payload"])
        return EmailMessage(
            message_id=message_id, sender=sender, subject=subject, attachments=attachments
        )

    def _extract_attachments(self, message_id: str, payload: dict) -> list[EmailAttachment]:
        attachments = []
        parts = payload.get("parts", [])

        for part in parts:
            filename = part.get("filename", "")
            body = part.get("body", {})

            if filename and body.get("attachmentId"):
                att = (
                    self.service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=message_id, id=body["attachmentId"])
                    .execute()
                )
                data = base64.urlsafe_b64decode(att["data"])
                attachments.append(
                    EmailAttachment(
                        filename=filename,
                        data=data,
                        mime_type=part.get("mimeType", "application/octet-stream"),
                    )
                )

            if "parts" in part:
                attachments.extend(self._extract_attachments(message_id, part))

        return attachments

    def mark_as_processed(self, message_id: str) -> None:
        """Đánh dấu đã đọc + gán nhãn, tránh pool lần sau"""
        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removedLabelIds": ["UNREAD"]},
            ).execute()
        except HttpError as e:
            if "No label" in str(e):
                logger.info(
                    "Message %s ko còn unread label (đã đọc từ trước) - bỏ qua", message_id
                )
            else:
                raise
