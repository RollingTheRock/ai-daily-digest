"""Email sending module for AI Daily Digest."""

from arxiv_sanity_bot.email.email_sender import EmailSender, SendGridEmailSender
from arxiv_sanity_bot.email.smtp_sender import SmtpEmailSender

__all__ = ["EmailSender", "SendGridEmailSender", "SmtpEmailSender"]
