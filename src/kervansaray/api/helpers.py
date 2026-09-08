"""API ortak yardimci fonksiyonlari."""


def parse_limit(raw: str | None, default: int = 50, max_limit: int = 100) -> int:
    """Query parametresinden limit parse eder.

    Gecersiz format veya pozitif olmayan degerlerde ValueError firlatir.
    """
    if raw is None:
        return default
    val = int(raw)
    if val <= 0:
        raise ValueError("limit must be positive")
    return min(val, max_limit)
