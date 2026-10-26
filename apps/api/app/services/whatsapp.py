import logging

logger = logging.getLogger(__name__)


def send_whatsapp_text(phone: str, text: str) -> None:
    """Temporary sender boundary; a later stage will replace this with Cloud API delivery."""
    logger.info("WhatsApp send stub: phone=%s text=%s", phone, text)
