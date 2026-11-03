from ..config import Settings
from .base import Calendar, format_description, parse_description
from .outlook import GraphAuth, NotLoggedInError, OutlookCalendar
from .shadow import ShadowCalendar

__all__ = [
    "Calendar",
    "GraphAuth",
    "NotLoggedInError",
    "OutlookCalendar",
    "ShadowCalendar",
    "format_description",
    "make_calendar",
    "parse_description",
]


def make_calendar(settings: Settings) -> Calendar:
    if settings.live:
        auth = GraphAuth(settings.ms_client_id, settings.token_cache)
        return OutlookCalendar(auth, settings.calendar_tag, settings.tz)
    return ShadowCalendar(settings.shadow_db, settings.calendar_tag)
