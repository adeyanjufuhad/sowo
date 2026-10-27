"""Chat with Sowo in the terminal, using your own Ollama. Nothing goes to WhatsApp or Paystack.

    python -m app.chat_cli

It uses the same agent, tools and server rules as the WhatsApp bot, on the database in DATABASE_URL, so it is
the quickest way to see how Qwen3 handles Pidgin, haggling and odd requests. Commands: /pay marks the
latest pending order paid (standing in for Paystack's webhook), /quit leaves.
"""

import sys

import httpx
from sqlalchemy import select

from app.config import get_settings, require_development
from app.db import SessionLocal, init_db
from app.models import Conversation, MessageRole, Order, OrderStatus
from app.seed import seed_data
from app.services import flow
from app.services.model import get_chat_model
from app.services.money import format_naira
from app.services.orders import mark_order_paid

DIM, RESET = "\033[2m", "\033[0m"


def check_ollama() -> str | None:
    """None if Ollama is up and has the model; otherwise what to do about it."""
    settings = get_settings()
    try:
        tags = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=5).json()
    except (httpx.HTTPError, ValueError):
        return f"Ollama isn't reachable at {settings.ollama_base_url}. Start it with: ollama serve"
    names = {model.get("name", "") for model in tags.get("models", [])}
    wanted = settings.ollama_model
    if wanted not in names and f"{wanted}:latest" not in names:
        return f"Ollama doesn't have {wanted} yet. Pull it with: ollama pull {wanted}"
    return None


def show_tools(tool_calls: list[dict] | None) -> None:
    for call in tool_calls or []:
        print(f"{DIM}  [{call['tool']}] {call['input']} -> {call['output']}{RESET}")


def pay_latest(session) -> None:
    order = session.scalar(select(Order).where(Order.status == OrderStatus.PENDING).order_by(Order.created_at.desc()))
    if order is None or order.paystack_reference is None:
        print("There is no pending order to pay.")
        return
    mark_order_paid(session, order.paystack_reference, order.total_kobo)
    session.commit()
    receipt = flow.finish_paid_order(session, order.id)
    print(f"{DIM}  [paystack] {format_naira(order.total_kobo)} paid for {order.paystack_reference}{RESET}")
    if receipt:
        print(f"\nSowo: {receipt.text}\n")


def main() -> int:
    require_development("The terminal chat (it seeds the demo shop)")
    settings = get_settings()
    problem = check_ollama() if settings.model_provider == "ollama" else None
    if problem:
        print(problem)
        return 1
    init_db()
    with SessionLocal() as session:
        vendor = seed_data(session)
        conversation = Conversation(
            vendor_id=vendor.id, customer_phone="cli-buyer", customer_name="You", is_simulator=True
        )
        session.add(conversation)
        session.commit()
        name = settings.llm_model if settings.model_provider == "openai" else settings.ollama_model
        print(f"Chatting with Sowo on {name}. Type /pay to pay, /quit to leave.\n")
        model = get_chat_model()
        while True:
            try:
                text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not text:
                continue
            if text == "/quit":
                return 0
            if text == "/pay":
                pay_latest(session)
                continue
            flow.add_message(session, conversation, MessageRole.BUYER, text)
            reply = flow.answer_buyer(session, conversation, model, settings, deliver=False)
            if reply is None:
                print(f"{DIM}  (Sowo is paused: the chat was handed to Ada){RESET}")
                continue
            show_tools(reply.tool_calls)
            print(f"\nSowo: {reply.text}\n")


if __name__ == "__main__":
    sys.exit(main())
