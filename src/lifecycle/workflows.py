import logging

from lifecycle.integrations import (
    GoogleWorkspaceClient,
    MDMClient,
    OktaClient,
    OnePasswordMock,
    SlackNotifier,
)
from lifecycle.models import ActionResult, WorkflowReport

LOG = logging.getLogger(__name__)


class LifecycleWorkflow:
    def __init__(
        self,
        settings,
        okta=None,
        google=None,
        onepassword=None,
        mdm=None,
        notifier=None,
    ):
        self.settings = settings
        self.okta = okta or OktaClient(settings)
        self.google = google or GoogleWorkspaceClient(settings)
        self.onepassword = onepassword or OnePasswordMock(settings)
        self.mdm = mdm or MDMClient(settings.mdm_provider)
        self.notifier = notifier or SlackNotifier(settings.slack_webhook_url)

    def onboard(
        self, first_name: str, last_name: str, email: str, password: str
    ) -> dict:
        report = WorkflowReport("onboarding", email)
        self._last_value = None
        if self.settings.dry_run:
            for system, action in [
                ("okta", "create_user_and_assign_group"),
                ("google_workspace", "create_user"),
                ("1password", "assign_vault_group"),
                ("mdm", "send_enrollment_invitation"),
            ]:
                report.add(
                    ActionResult(
                        system, action, True, "dry-run; no API call made", True
                    )
                )
            return report.to_dict()

        self._run(
            report,
            "okta",
            "create_user",
            lambda: self.okta.create_user(first_name, last_name, email, password),
        )
        self._run(
            report,
            "okta",
            "assign_group",
            lambda: self.okta.assign_group(
                self._last_value, self.settings.okta_group_name
            ),
            requires_previous=True,
        )
        self._run(
            report,
            "google_workspace",
            "create_user",
            lambda: self.google.create_user(first_name, last_name, email, password),
        )
        self._run(
            report,
            "1password",
            "assign_vault_group",
            lambda: self.onepassword.assign_new_hire(email),
        )
        self._run(
            report,
            "mdm",
            "send_enrollment_invitation",
            lambda: self.mdm.send_enrollment_invitation(email, first_name, last_name),
        )
        return report.to_dict()

    def offboard(self, email: str) -> dict:
        report = WorkflowReport("offboarding", email)
        if self.settings.dry_run:
            for system, action in [
                ("okta", "deactivate_user"),
                ("google_workspace", "revoke_all_oauth_tokens"),
                ("1password", "remove_from_all_shared_vaults"),
                ("slack", "send_completion_alert"),
            ]:
                report.add(
                    ActionResult(
                        system, action, True, "dry-run; no API call made", True
                    )
                )
            return report.to_dict()

        self._run(
            report, "okta", "deactivate_user", lambda: self.okta.deactivate_user(email)
        )
        self._run(
            report,
            "google_workspace",
            "revoke_all_oauth_tokens",
            lambda: self.google.revoke_tokens(email),
        )
        self._run(
            report,
            "1password",
            "remove_from_all_shared_vaults",
            lambda: self.onepassword.remove_from_shared_vaults(email),
        )
        try:
            sent = self.notifier.send(report.to_dict())
            report.add(
                ActionResult(
                    "slack",
                    "send_completion_alert",
                    True,
                    "webhook delivered"
                    if sent
                    else "webhook not configured; summary logged",
                    simulated=not sent,
                )
            )
        except Exception as exc:
            LOG.exception("slack.send_completion_alert failed")
            report.add(ActionResult("slack", "send_completion_alert", False, str(exc)))
        return report.to_dict()

    def _run(self, report, system, action, operation, requires_previous=False):
        try:
            if requires_previous and not hasattr(self, "_last_value"):
                raise RuntimeError("Skipped because preceding identity creation failed")
            value = operation()
            if system == "okta" and action == "create_user":
                self._last_value = value
            report.add(
                ActionResult(
                    system,
                    action,
                    True,
                    str(value) if value is not None else "completed",
                )
            )
        except Exception as exc:  # continue to reconcile remaining systems
            LOG.exception("%s.%s failed", system, action)
            report.add(ActionResult(system, action, False, str(exc)))
