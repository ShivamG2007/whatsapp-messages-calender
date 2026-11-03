import logging
import time as time_module
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import msal
import requests

from ..models import CalendarEvent
from .base import fill_from_description, is_bot_description

log = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Calendars.ReadWrite"]
AUTHORITY = "https://login.microsoftonline.com/consumers"


class NotLoggedInError(RuntimeError):
    pass


class GraphAuth:
    """Sign-in for a personal Microsoft account using the device-code flow (no browser redirect needed)."""

    def __init__(self, client_id: str, cache_path: Path):
        if not client_id:
            raise NotLoggedInError("MS_CLIENT_ID is empty. Register the app first (docs/SETUP.md, step 'Outlook').")
        self.cache_path = cache_path
        self.cache = msal.SerializableTokenCache()
        if cache_path.exists():
            self.cache.deserialize(cache_path.read_text())
        self.app = msal.PublicClientApplication(client_id, authority=AUTHORITY, token_cache=self.cache)

    def _save(self) -> None:
        if self.cache.has_state_changed:
            self.cache_path.write_text(self.cache.serialize())

    def login(self) -> str:
        flow = self.app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Could not start sign-in: {flow.get('error_description', flow)}")
        print(flow["message"], flush=True)
        result = self.app.acquire_token_by_device_flow(flow)
        self._save()
        if "access_token" not in result:
            raise RuntimeError(f"Sign-in failed: {result.get('error_description', result)}")
        return result.get("id_token_claims", {}).get("preferred_username", "your account")

    def token(self) -> str:
        accounts = self.app.get_accounts()
        result = self.app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
        self._save()
        if not result or "access_token" not in result:
            raise NotLoggedInError("Not signed in to Outlook. Run: python -m brain login")
        return result["access_token"]


def _graph_time(value: dict) -> datetime:
    return datetime.fromisoformat(value["dateTime"][:19]).replace(tzinfo=UTC)


class OutlookCalendar:
    def __init__(self, auth: GraphAuth, tag: str, tz: ZoneInfo, session: requests.Session | None = None):
        self.auth = auth
        self.tag = tag
        self.tz = tz
        self.session = session or requests.Session()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.auth.token()}"
        headers["Prefer"] = 'outlook.timezone="UTC", outlook.body-content-type="text"'
        if not url.startswith("http"):
            url = GRAPH + url
        for attempt in range(3):
            response = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                wait = int(response.headers.get("Retry-After", 2**attempt))
                log.warning("Graph returned %s, retrying in %ss", response.status_code, wait)
                time_module.sleep(wait)
                continue
            response.raise_for_status()
            return response
        response.raise_for_status()
        return response

    def _to_event(self, item: dict) -> CalendarEvent:
        all_day = bool(item.get("isAllDay"))
        start, end = _graph_time(item["start"]), _graph_time(item["end"])
        if all_day:
            start = start.replace(tzinfo=self.tz)
            end = end.replace(tzinfo=self.tz)
        else:
            start, end = start.astimezone(self.tz), end.astimezone(self.tz)
        event = CalendarEvent(
            id=item["id"],
            title=item.get("subject") or "",
            start=start,
            end=end,
            place=(item.get("location") or {}).get("displayName", ""),
            all_day=all_day,
            description=(item.get("body") or {}).get("content", ""),
        )
        return fill_from_description(event)

    def _is_ours(self, item: dict) -> bool:
        body = (item.get("body") or {}).get("content", "")
        return self.tag in (item.get("categories") or []) and is_bot_description(body, self.tag)

    def _payload(self, event: CalendarEvent) -> dict:
        if event.all_day:
            start = {"dateTime": event.start.strftime("%Y-%m-%dT00:00:00"), "timeZone": "UTC"}
            end = {"dateTime": event.end.strftime("%Y-%m-%dT00:00:00"), "timeZone": "UTC"}
        else:
            start = {"dateTime": event.start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"}
            end = {"dateTime": event.end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"}
        return {
            "subject": event.title,
            "body": {"contentType": "text", "content": event.description},
            "start": start,
            "end": end,
            "isAllDay": event.all_day,
            "location": {"displayName": event.place},
            "categories": [self.tag],
            "isReminderOn": not event.all_day,
            "reminderMinutesBeforeStart": 30,
        }

    def list_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        params = {
            "startDateTime": start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "$select": "id,subject,start,end,location,body,categories,isAllDay",
            "$top": "100",
        }
        url, events = "/me/calendarView", []
        while url:
            data = self._request("GET", url, params=params).json()
            events += [self._to_event(item) for item in data.get("value", []) if self._is_ours(item)]
            url, params = data.get("@odata.nextLink"), None
        return sorted(events, key=lambda e: e.start)

    def create(self, event: CalendarEvent) -> CalendarEvent:
        item = self._request("POST", "/me/events", json=self._payload(event)).json()
        event.id = item["id"]
        return event

    def update(self, event: CalendarEvent) -> CalendarEvent:
        self._ensure_ours(event.id)
        self._request("PATCH", f"/me/events/{event.id}", json=self._payload(event))
        return event

    def delete(self, event_id: str) -> None:
        self._ensure_ours(event_id)
        self._request("DELETE", f"/me/events/{event_id}")

    def _ensure_ours(self, event_id: str) -> None:
        item = self._request("GET", f"/me/events/{event_id}", params={"$select": "id,body,categories"}).json()
        if not self._is_ours(item):
            raise PermissionError(f"Refusing to touch event {event_id}: it was not created by the bot.")
