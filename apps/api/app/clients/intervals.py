from __future__ import annotations

from datetime import date
import httpx


class IntervalsClient:
    def __init__(self, base_url: str, api_key: str, athlete_id: str = "0", timeout_s: float = 30.0):
        if not api_key:
            raise ValueError("INTERVALS_API_KEY is not configured")
        self.base_url = base_url.rstrip("/")
        self.athlete_id = athlete_id
        self.auth = httpx.BasicAuth("API_KEY", api_key)
        self.timeout_s = timeout_s

    def list_activities(self, oldest: date, newest: date) -> list[dict]:
        url = f"{self.base_url}/athlete/{self.athlete_id}/activities"
        response = httpx.get(
            url,
            params={"oldest": oldest.isoformat(), "newest": newest.isoformat()},
            auth=self.auth,
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return []
        return response.json()
