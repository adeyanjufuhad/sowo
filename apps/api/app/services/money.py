"""Money is integer kobo everywhere. This is the one place it becomes text for people to read."""


def format_naira(kobo: int) -> str:
    """4350000 -> '₦43,500'. Kobo are shown only when they are not zero: 4350050 -> '₦43,500.50'."""
    if isinstance(kobo, bool) or not isinstance(kobo, int):
        raise TypeError(f"format_naira expects integer kobo, got {kobo!r}")
    sign = "-" if kobo < 0 else ""
    naira, remainder = divmod(abs(kobo), 100)
    fraction = f".{remainder:02d}" if remainder else ""
    return f"{sign}₦{naira:,}{fraction}"
