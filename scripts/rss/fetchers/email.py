"""Fetch RSS entries from an IMAP mailbox."""
import imaplib
import os
import re
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

URL_RE = re.compile(r"https?://[^\s<>\"']+")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _decode_part_payload(part) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    for enc in (charset, "utf-8", "latin-1"):
        try:
            return payload.decode(enc, errors="replace")
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    text = HTML_TAG_RE.sub(" ", html)
    return re.sub(r"\s+", " ", text).strip()


def _extract_body(msg) -> tuple[str, str]:
    """返回 (plain_text, html_text)。"""
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition.lower():
                continue
            ctype = part.get_content_type()
            text = _decode_part_payload(part)
            if not text:
                continue
            if ctype == "text/plain":
                plain_parts.append(text)
            elif ctype == "text/html":
                html_parts.append(text)
    else:
        text = _decode_part_payload(msg)
        if msg.get_content_type() == "text/html":
            html_parts.append(text)
        else:
            plain_parts.append(text)

    plain = "\n\n".join(p.strip() for p in plain_parts if p.strip())
    html = "\n\n".join(p.strip() for p in html_parts if p.strip())
    return plain, html


def _first_url(*texts: str) -> str | None:
    for text in texts:
        if not text:
            continue
        match = URL_RE.search(text)
        if match:
            return match.group(0).rstrip(").,;]")
    return None


def _truncate(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _resolve_env(source: dict, env_key: str) -> str:
    env_name = source.get(env_key)
    if not env_name:
        return ""
    return (os.getenv(str(env_name)) or "").strip()


def _build_search_criteria(source: dict) -> str:
    parts: list[str] = []
    criteria = source.get("criteria")
    if criteria:
        return str(criteria)

    since_days = source.get("since_days")
    if since_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=int(since_days))
        parts.append(f'SINCE {since.strftime("%d-%b-%Y")}')

    from_filter = source.get("from_filter")
    if from_filter:
        parts.append(f'FROM "{from_filter}"')

    subject_filter = source.get("subject_filter")
    if subject_filter:
        parts.append(f'SUBJECT "{subject_filter}"')

    if not parts:
        return "ALL"
    return f"({' '.join(parts)})"


def _format_published(msg) -> str | None:
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")
    except (TypeError, ValueError, IndexError):
        return None


def _needs_imap_id(host: str, source: dict) -> bool:
    if "imap_id" in source:
        return bool(source["imap_id"])
    host = host.lower()
    return any(domain in host for domain in ("163.com", "126.com", "yeah.net"))


def _send_imap_id(mail) -> None:
    """网易系邮箱要求客户端发送 IMAP ID，否则 SELECT 会失败。"""
    if "ID" not in imaplib.Commands:
        imaplib.Commands["ID"] = ("AUTH",)
    mail._simple_command(
        "ID",
        '("name" "rsshub" "version" "1.0" "contact" "rsshub@local" "vendor" "rsshub")',
    )


def fetch_entries_from_email(source: dict) -> list[dict]:
    """从 IMAP 邮箱拉取邮件并转为 RSS 条目."""
    if not source or source.get("type") != "email":
        return []

    host = _resolve_env(source, "host_env")
    user = _resolve_env(source, "user_env")
    password = _resolve_env(source, "password_env")
    if not host or not user or not password:
        raise ValueError(
            "email 源需配置 host_env、user_env、password_env，"
            "并在 .env 或环境变量中提供对应值"
        )

    folder = source.get("folder") or source.get("mailbox") or "INBOX"
    port = int(source.get("port", 993))
    use_ssl = source.get("ssl", True)
    limit = int(source.get("limit", 50))
    summary_max_chars = int(source.get("summary_max_chars", 500))
    prefer_plain = source.get("body_format", "plain") != "html"
    link_from_body = source.get("link_from_body", True)

    if use_ssl:
        mail = imaplib.IMAP4_SSL(host, port)
    else:
        mail = imaplib.IMAP4(host, port)

    try:
        mail.login(user, password)
        if _needs_imap_id(host, source):
            _send_imap_id(mail)
        status, _ = mail.select(folder, readonly=True)
        if status != "OK":
            raise ValueError(f"无法打开邮箱文件夹: {folder}")

        criteria = _build_search_criteria(source)
        status, data = mail.search(None, criteria)
        if status != "OK":
            raise ValueError(f"IMAP 搜索失败: {criteria}")

        ids = data[0].split()
        if not ids:
            return []

        ids = ids[-limit:]
        ids.reverse()

        entries: list[dict] = []
        for msg_id in ids:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                continue

            msg = message_from_bytes(raw)
            title = _decode_mime_header(msg.get("Subject"))
            if not title:
                continue

            plain, html = _extract_body(msg)
            if prefer_plain:
                summary_source = plain or _strip_html(html)
            else:
                summary_source = html or plain

            entry: dict = {"title": title}
            published = _format_published(msg)
            if published:
                entry["published"] = published

            if summary_source:
                entry["summary"] = _truncate(summary_source, summary_max_chars)

            if link_from_body:
                link = _first_url(plain, html)
                if link:
                    entry["link"] = link

            entries.append(entry)
        return entries
    finally:
        try:
            mail.logout()
        except Exception:
            pass
