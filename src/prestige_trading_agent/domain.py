from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class FunnelPath(StrEnum):
    UNKNOWN = "unknown"
    NEWBIE = "newbie"
    COURSE = "course"
    INDICATOR = "indicator"


class FunnelState(StrEnum):
    NEW = "new"
    QUALIFYING = "qualifying"
    FORM_PENDING = "form_pending"
    FORM_COMPLETED = "form_completed"
    FREE_COMMUNITY = "free_community"
    CHECKOUT_PENDING = "checkout_pending"
    PAID_ACTIVE = "paid_active"
    TRIAL_PENDING = "trial_pending"
    TRIAL_APPROVED = "trial_approved"
    HUMAN_HANDOFF = "human_handoff"
    UNSUBSCRIBED = "unsubscribed"


class NextAction(StrEnum):
    NONE = "none"
    SEND_FORM = "send_form"
    SEND_CHECKOUT = "send_checkout"
    SEND_FREE_LINE_INVITE = "send_free_line_invite"
    CREATE_ACCESS_REQUEST = "create_access_request"
    HUMAN_HANDOFF = "human_handoff"
    SEND_PAID_ROOM = "send_paid_room"


class OutboxKind(StrEnum):
    SEND_MESSAGE = "send_message"
    SEND_FREE_LINE_INVITE = "send_free_line_invite"
    ENROLL_LMS = "enroll_lms"
    PROVISION_PAID_ACCESS = "provision_paid_access"
    NOTIFY_ACCESS_APPROVED = "notify_access_approved"


class AccessStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ChatRequest(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=4000)


class FormCompletion(BaseModel):
    submission_id: str
    external_id: str
    email: EmailStr | None = None
    path: FunnelPath
    data: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    reviewed_by: str = Field(min_length=1, max_length=255)
    note: str | None = None


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
