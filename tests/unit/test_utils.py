from unittest.mock import MagicMock, patch

from app.utils import send_email


def test_send_email_with_valid_inputs():
    """Test that send_email successfully sends an email with valid inputs."""
    with patch(
        "app.utils.SMTP_CONFIG",
        {
            "server": "smtp.example.com",
            "port": 587,
            "use_tls": True,
            "username": "user",
            "password": "pass",
            "default_sender": "noreply@example.com",
            "recipient": "admin@example.com",
        },
    ):
        with patch("app.utils.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = send_email(
                recipient="test@example.com",
                subject="Test Subject",
                body="Test message body",
                sender="sender@example.com",
            )

            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once()
            mock_server.sendmail.assert_called_once()


def test_send_email_handles_smtp_exception():
    """Test that send_email returns False when SMTP fails."""
    with patch("app.utils.smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__.side_effect = Exception("SMTP error")

        result = send_email(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test message",
            sender="sender@example.com",
        )

        assert result is False


def test_send_email_validates_recipient_format():
    """Test that send_email validates email format."""
    result = send_email(
        recipient="invalid-email",
        subject="Test",
        body="Test",
        sender="sender@example.com",
    )

    assert result is False
