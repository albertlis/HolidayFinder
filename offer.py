from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Offer:
    link: str
    title: str
    price_str: str
    category: str