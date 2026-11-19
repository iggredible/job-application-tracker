import enum

from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all tables."""


def enum_type(enum_class: type[enum.Enum], name: str) -> Enum:
    # Store the lowercase values, not the member names, to match the documented schema.
    return Enum(
        enum_class,
        name=name,
        values_callable=lambda members: [m.value for m in members],
    )
