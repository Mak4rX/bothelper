"""Схеми змін: порядок полів і підписи для денної/нічної зміни."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShiftScheme:
    code: str            # "day" | "night"
    title: str           # "Денна зміна" | "Нічна зміна"
    open_label: str      # підпис початкової каси
    earned_label: str    # "Зароблено за день/ніч готівки"
    close_label: str     # підпис кінцевої каси


DAY = ShiftScheme(
    code="day",
    title="Денна зміна",
    open_label="Каса готівки зранку",
    earned_label="Зароблено за день готівки",
    close_label="Каса готівки вечері",
)

NIGHT = ShiftScheme(
    code="night",
    title="Нічна зміна",
    open_label="Каса готівки вечері",
    earned_label="Зароблено за ніч готівки",
    close_label="Каса готівки зранку",
)

SCHEMES: dict[str, ShiftScheme] = {s.code: s for s in (DAY, NIGHT)}


def fmt(amount: int) -> str:
    """7 791 — формат числа з роздільником тисяч (як у звіті)."""
    return f"{amount:,}".replace(",", " ")


def build_report(scheme: ShiftScheme, open_cash: int, close_cash: int,
                 expenses: int, senet: int,
                 collection: int = 0) -> tuple[str, int, int]:
    """
    Повертає (текст_звіту, зароблено_розраховане, надлишок).

    close_cash — фізична каса наприкінці зміни (те що полічив).
    Зароблено = close_cash − open_cash + expenses + інкасація.
    Надлишок  = зароблено − сенет  (плюс = надлишок, мінус = недостача).
    """
    earned = close_cash - open_cash + expenses + collection
    surplus = earned - senet

    lines = [
        "Закриття зміни.",
        f"{scheme.open_label}: {fmt(open_cash)}",
        f"{scheme.earned_label}: {fmt(earned)}",
        f"Торгівельні витрати: {fmt(expenses)}",
    ]
    if collection:
        lines.append(f"Інкасація: {fmt(collection)}")
    lines.append(f"{scheme.close_label}: {fmt(close_cash)}")
    lines.append(f"Нараховано у сенеті: {fmt(senet)}")

    if surplus > 0:
        lines.append(f"{fmt(surplus)} грн надлишку.")
    elif surplus < 0:
        lines.append(f"{fmt(-surplus)} грн недостачі.")
    else:
        lines.append("Каса сходиться ✅")

    return "\n".join(lines), earned, surplus
