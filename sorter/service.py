"""Background polling orchestrator service for email monitoring and alert dispatch."""

import logging
import time
from typing import Sequence

from sorter.alerter import format_whatsapp_message, send_whatsapp_alert
from sorter.classifier import classify_email
from sorter.config import Config
from sorter.email_fetcher import fetch_unseen_emails
from sorter.storage import Storage

logger = logging.getLogger(__name__)


class EmailMonitorService:
    """Service to poll configured email accounts, classify new messages, and dispatch alerts."""

    def __init__(self, config: Config, storage: Storage):
        self.config = config
        self.storage = storage

    def poll_account(
        self, account_name: str, user: str, password: str, alert_new: bool = True
    ) -> int:
        """Poll a single Gmail account for unseen emails and process them.

        Args:
            account_name: Logical account identifier (e.g. 'College', 'Personal')
            user: Gmail address / username
            password: App password
            alert_new: If True, classify and dispatch WhatsApp alert for alert-worthy emails.
                       If False (baseline mode), record email as processed without alerting.

        Returns:
            Count of WhatsApp alerts dispatched.
        """
        logger.info("Polling account '%s' (%s)...", account_name, user)
        alerts_sent = 0

        try:
            unseen_emails = fetch_unseen_emails(user, password)
        except Exception as e:
            logger.error(
                "Network, IMAP, or SSL error while fetching emails for %s: %s",
                account_name,
                e,
                exc_info=True,
            )
            return 0

        logger.info(
            "Fetched %d unseen email(s) from account '%s'.",
            len(unseen_emails),
            account_name,
        )

        for email_data in unseen_emails:
            message_id = email_data.message_id
            if self.storage.is_processed(account_name, message_id):
                logger.debug(
                    "Skipping already processed email [%s] ID: %s",
                    account_name,
                    message_id,
                )
                continue

            if not alert_new:
                # Baseline sync: mark as processed without running LLM or dispatching alert
                self.storage.mark_processed(
                    account=account_name,
                    message_id=message_id,
                    subject=email_data.subject,
                    alerted=False,
                )
                logger.info(
                    "Baseline sync: marked [%s] '%s' (%s) as processed (no alert).",
                    account_name,
                    email_data.subject,
                    message_id,
                )
                continue

            # Classify incoming email with Groq LLaMA
            try:
                decision = classify_email(email_data, self.config.groq_api_key)
            except Exception as e:
                logger.error(
                    "Failed to classify email [%s] ID %s: %s",
                    account_name,
                    message_id,
                    e,
                    exc_info=True,
                )
                continue

            alerted = False
            if decision.is_alert_worthy:
                logger.info(
                    "Email [%s] '%s' is alert-worthy (%s, urgency=%s). Formatting alert...",
                    account_name,
                    email_data.subject,
                    decision.category,
                    decision.urgency,
                )
                formatted_msg = format_whatsapp_message(
                    account=account_name,
                    email_data=email_data,
                    decision=decision,
                )

                try:
                    sent_ok = send_whatsapp_alert(
                        phone=self.config.callmebot_phone,
                        api_key=self.config.callmebot_api_key,
                        message=formatted_msg,
                    )
                    if sent_ok:
                        alerts_sent += 1
                        alerted = True
                    else:
                        logger.warning(
                            "Failed to deliver WhatsApp alert for email [%s] ID %s; will retry on next polling cycle.",
                            account_name,
                            message_id,
                        )
                        continue
                except Exception as e:
                    logger.warning(
                        "Unexpected error sending WhatsApp alert for [%s] ID %s: %s; will retry on next polling cycle.",
                        account_name,
                        message_id,
                        e,
                        exc_info=True,
                    )
                    continue
            else:
                logger.info(
                    "Email [%s] '%s' categorized as '%s' (not alert-worthy).",
                    account_name,
                    email_data.subject,
                    decision.category,
                )

            # Record in storage as processed
            self.storage.mark_processed(
                account=account_name,
                message_id=message_id,
                subject=email_data.subject,
                alerted=alerted,
            )

        return alerts_sent

    def run_once(self, alert_new: bool = True) -> int:
        """Run a single polling cycle across all configured accounts.

        Returns:
            Total count of alerts sent across all accounts.
        """
        accounts = [
            ("College", self.config.college_user, self.config.college_pass),
            ("Personal", self.config.personal_user, self.config.personal_pass),
        ]

        total_alerts = 0
        for name, user, pwd in accounts:
            try:
                alerts = self.poll_account(name, user, pwd, alert_new=alert_new)
                total_alerts += alerts
            except Exception as e:
                logger.error(
                    "Unhandled exception during polling account '%s': %s",
                    name,
                    e,
                    exc_info=True,
                )

        return total_alerts

    def start(self) -> None:
        """Start continuous polling loop honoring configured interval."""
        interval = self.config.poll_interval_seconds
        logger.info(
            "Starting EmailMonitorService daemon (polling interval: %d seconds)...",
            interval,
        )

        try:
            while True:
                logger.info("Starting polling cycle...")
                try:
                    alerts = self.run_once(alert_new=True)
                    logger.info("Polling cycle finished. Alerts dispatched: %d", alerts)
                except Exception as e:
                    logger.error(
                        "Unexpected error during polling cycle: %s", e, exc_info=True
                    )

                logger.info("Sleeping for %d seconds until next poll...", interval)
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("EmailMonitorService daemon stopped by user (SIGINT / KeyboardInterrupt).")
