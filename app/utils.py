"""Utility helpers shared across the catalog app."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from typing import Callable, TypeVar
from uuid import UUID
from xml.etree import ElementTree

from flask import Response, jsonify

F = TypeVar("F", bound=Callable[..., Response])


def is_valid_uuid4(uuid_string: str) -> bool:
    """Return True if the string is a valid UUID4, otherwise False."""

    try:
        return str(UUID(uuid_string, version=4)) == uuid_string
    except ValueError:
        return False
    except AttributeError:
        return False


def json_not_found() -> Response:
    return jsonify({"error": "Not Found"}), 404


def valid_id_required(func: F) -> F:
    """Decorator that ensures all route params are valid UUID4 values."""

    @wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore[misc]
        for arg in args:
            if not is_valid_uuid4(arg):
                return json_not_found()
        for value in kwargs.values():
            if not is_valid_uuid4(value):
                return json_not_found()
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def dict_from_hint(hint_string):
    """Compute a dict of args from our hint string.

    The hint string is a base64 encoded JSON string. An argument of None
    returns an empty dict and if there is an error decoding the hint,
    it also returns an empty dict.
    """
    if hint_string is None:
        return dict()

    try:
        return json.loads(base64.urlsafe_b64decode(hint_string).decode("utf-8"))
    except ValueError:
        return dict()


def hint_from_dict(args_dict):
    """Compute our URL hint from a dict of args.

    The hint string is a base64 encoded JSON string.
    """
    return base64.urlsafe_b64encode(
        json.dumps(args_dict, separators=(",", ":")).encode("utf-8")
    ).decode("utf-8")


def normalize_site_url(site_url: str) -> str:
    return site_url.strip("https://")


def pop_doc_by_identifier(os_docs: list, identifier: str) -> dict | None:
    """
    get the parent dataset from the collection by popping it from the list. this
    changes the input list in place by removing parent doc
    """
    for idx, doc in enumerate(os_docs):
        if doc.get("identifier") == identifier:
            return os_docs.pop(idx)


def register_iso_namespaces(element_tree: ElementTree) -> None:
    """
    registers ISO19115 namespaces to the element tree so they're present
    when displaying xml files in the browser instead of defaults
    (e.g. ns0, ns1, ns2, etc...). "gmi" is just for ISO19115-2 and not -1
    but it's harmless to register it instead of sniffing the file and determining
    which ISO record it is.
    """
    namespaces = {
        "gmi": "http://www.isotc211.org/2005/gmi",
        "gmd": "http://www.isotc211.org/2005/gmd",
        "gco": "http://www.isotc211.org/2005/gco",
        "gml": "http://www.opengis.net/gml/3.2",
        "gsr": "http://www.isotc211.org/2005/gsr",
        "gss": "http://www.isotc211.org/2005/gss",
        "gst": "http://www.isotc211.org/2005/gst",
        "gmx": "http://www.isotc211.org/2005/gmx",
        "gfc": "http://www.isotc211.org/2005/gfc",
        "srv": "http://www.isotc211.org/2005/srv",
        "xlink": "http://www.w3.org/1999/xlink",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    for ns, ns_url in namespaces.items():
        element_tree.register_namespace(ns, ns_url)


logger = logging.getLogger(__name__)

SMTP_CONFIG = {
    "server": os.getenv("SMTP_SERVER"),
    "port": int(os.getenv("SMTP_PORT", 587)),
    "use_tls": os.getenv("SMTP_STARTTLS", "true").lower() == "true",
    "username": os.getenv("SMTP_USER"),
    "password": os.getenv("SMTP_PASSWORD"),
    "default_sender": os.getenv("SMTP_SENDER", "noreply@data.gov"),
    "recipient": os.getenv("SMTP_RECIPIENT", "DataGovHelp@gsa.gov"),
}


def validate_email(email):
    """Validate email format using simple regex."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def send_email(recipient, subject, body, sender=None):
    """
    Send an email via SMTP.

    Args:
        recipient: Email address to send to
        subject: Email subject line
        body: Email body text
        sender: Email address to send from (defaults to SMTP_SENDER env var)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not validate_email(recipient):
        logger.error(f"Invalid recipient email format: {recipient}")
        return False

    if not all(
        [SMTP_CONFIG["server"], SMTP_CONFIG["username"], SMTP_CONFIG["password"]]
    ):
        logger.error("SMTP configuration is incomplete")
        return False

    if not sender:
        sender = SMTP_CONFIG["default_sender"]

    try:
        with smtplib.SMTP(SMTP_CONFIG["server"], SMTP_CONFIG["port"]) as server:
            if SMTP_CONFIG["use_tls"]:
                server.starttls()
            server.login(SMTP_CONFIG["username"], SMTP_CONFIG["password"])

            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = recipient
            msg["Reply-To"] = "no-reply@gsa.gov"
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            server.sendmail(sender, [recipient], msg.as_string())

        logger.info(f"Email sent successfully to {recipient}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
