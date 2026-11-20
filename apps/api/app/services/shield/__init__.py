"""Scam Shield: deterministic checks on what buyers send. guard.py checks Sowo's replies; this checks the buyer's.

High-severity finds (asking for a code or PIN, pretending to be a bank or Paystack) hand the chat to the vendor and
Sowo stops replying. Medium ones are flagged for the vendor and the chat carries on; nothing a buyer says ever marks
an order paid or moves stock, whatever the shield finds.
"""
