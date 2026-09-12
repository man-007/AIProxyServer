from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ModelInfo:
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "upstream"
    available: bool = True
    capabilities: dict[str, Any] = field(default_factory=lambda: {
        "chat": True,
        "streaming": True,
        "tool_calling": False,
        "vision": False,
        "structured_output": False,
        "reasoning": False,
    })
    source: str = "upstream"
    compatibility_status: str = "unknown"
    last_seen: str = ""

    @classmethod
    def from_upstream(cls, record: dict[str, Any]) -> "ModelInfo":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            id=record.get("id", "unknown"),
            object=record.get("object", "model"),
            created=int(record.get("created", 0) or 0),
            owned_by=record.get("owned_by", "upstream"),
            available=bool(record.get("available", True)),
            source="upstream",
            compatibility_status="unknown",
            last_seen=now,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "owned_by": self.owned_by,
            "available": self.available,
            "capabilities": self.capabilities,
            "source": self.source,
            "compatibility_status": self.compatibility_status,
            "last_seen": self.last_seen,
        }
