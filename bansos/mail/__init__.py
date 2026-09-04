"""Pilih penyedia temp-mail dari config."""

from __future__ import annotations

from ..config import Settings
from .base import MailProvider
from .mailtm import MailTmMail
from .worker import WorkerMail

__all__ = ["MailProvider", "make_mail"]


def make_mail(config: Settings) -> MailProvider:
    if config.mail_provider == "mailtm":
        print(f"📬 Temp-mail: mail.tm ({config.mailtm_base_url})")
        return MailTmMail(config.mailtm_base_url)
    print(f"📬 Temp-mail: worker pribadi ({config.mail_worker_url})")
    return WorkerMail(config.mail_worker_url, config.mail_worker_password)
