"""Calendário operacional da colônia, independente do fuso do servidor."""
from datetime import datetime
from zoneinfo import ZoneInfo


TIME_ZONE = ZoneInfo("America/Sao_Paulo")


def now():
    return datetime.now(TIME_ZONE)


def today():
    return now().date()
