from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ActionResult:
    system: str
    action: str
    success: bool
    detail: str = ""
    simulated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowReport:
    workflow: str
    user: str
    timestamp: str = field(default_factory=utc_now)
    actions: list[ActionResult] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def add(self, result: ActionResult) -> None:
        self.actions.append(result)
        if not result.success:
            self.failures.append(f"{result.system}.{result.action}: {result.detail}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "user": self.user,
            "timestamp": self.timestamp,
            "actions": [item.to_dict() for item in self.actions],
            "failures": self.failures,
            "status": "completed_with_errors" if self.failures else "completed",
        }
