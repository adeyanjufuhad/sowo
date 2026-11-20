"""Run the rules on a buyer's message in its conversation, and keep what they find as flags for the vendor."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Conversation, Message, Order, OrderStatus, ShieldFlag
from app.services.shield.rules import Finding, claims_payment, scan_text


def inspect(
    session: Session, conversation: Conversation, message: Message, settings: Settings, *, image: bool = False
) -> list[Finding]:
    """Every finding for this message (flagged once per rule until the vendor resolves it). Commits."""
    findings = scan_text(message.text, settings.shield_allowed_domains)
    unpaid = session.scalar(
        select(Order.id).where(Order.conversation_id == conversation.id, Order.status == OrderStatus.PENDING).limit(1)
    )
    if unpaid and (image or claims_payment(message.text)):
        findings.append(Finding("UNVERIFIED_PAYMENT", "medium", "a picture" if image else message.text[:300]))
    failed = session.scalar(
        select(func.count(Order.id)).where(
            Order.conversation_id == conversation.id, Order.status.in_([OrderStatus.EXPIRED, OrderStatus.CANCELLED])
        )
    )
    if failed and failed >= 2:
        findings.append(Finding("REPEATED_FAILED_PAYMENTS", "medium", f"{failed} payments failed or expired"))

    open_rules = set(
        session.scalars(
            select(ShieldFlag.rule).where(
                ShieldFlag.conversation_id == conversation.id, ShieldFlag.resolved_at.is_(None)
            )
        )
    )
    for finding in findings:
        if finding.rule not in open_rules:
            open_rules.add(finding.rule)
            session.add(
                ShieldFlag(
                    conversation_id=conversation.id,
                    message_id=message.id,
                    rule=finding.rule,
                    severity=finding.severity,
                    evidence=finding.evidence[:300],
                )
            )
    session.commit()
    return findings
