"""Helpers for driving the web interface in tests."""

import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

CSRF_RE = re.compile(r'name="csrf_token"\s+value="([^"]+)"')


class UI:
    """Wraps the Flask test client: fetches the form first, submits with its CSRF token."""

    def __init__(self, client):
        self.client = client

    # -- plain requests -------------------------------------------------------
    def get(self, url, **kwargs):
        kwargs.setdefault("base_url", "https://localhost")
        return self.client.get(url, **kwargs)

    def soup(self, response) -> BeautifulSoup:
        return BeautifulSoup(response.get_data(as_text=True), "html.parser")

    def token(self, url: str) -> str:
        response = self.get(url)
        match = CSRF_RE.search(response.get_data(as_text=True))
        assert match, f"no CSRF token on {url} (status {response.status_code})"
        return match.group(1)

    # -- form submission ----------------------------------------------------------
    def post(self, url, data=None, *, form_url=None, token=True, follow=False, **kwargs):
        """POST like a browser: load the form page (``form_url`` or ``url``) for its token."""
        data = dict(data or {})
        if token is True:
            data["csrf_token"] = self.token(form_url or url)
        elif token:
            data["csrf_token"] = token
        kwargs.setdefault("base_url", "https://localhost")
        # Browsers send a Referer on form posts; Flask-WTF requires it for https requests.
        kwargs.setdefault("headers", {"Referer": f"https://localhost{form_url or url}"})
        return self.client.post(url, data=data, follow_redirects=follow, **kwargs)

    def submit(self, url, data, *, follow=True, **kwargs):
        """Fill and submit a create/edit form; follows the redirect by default."""
        return self.post(url, data, follow=follow, **kwargs)

    def delete(self, entity_url: str, *, next_url: str | None = None, follow=True):
        """Two-step delete: open the confirmation page, then confirm."""
        confirm_url = f"{entity_url}/loeschen" + (f"?next={next_url}" if next_url else "")
        page = self.get(confirm_url)
        assert page.status_code == 200, f"delete confirmation not available ({page.status_code})"
        return self.post(confirm_url, {"next": next_url or ""} if next_url else {}, form_url=confirm_url, follow=follow)

    # -- session ------------------------------------------------------------------
    def login(self, login: str, password: str, *, follow=False):
        return self.post("/login", {"login": login, "password": password}, follow=follow)

    def logout(self):
        return self.post("/logout", form_url="/")

    # -- response helpers -----------------------------------------------------------
    @staticmethod
    def location(response) -> str:
        return urlsplit(response.headers["Location"]).path

    @staticmethod
    def flashes(soup: BeautifulSoup) -> list[str]:
        return [el.get_text(strip=True) for el in soup.select(".flash")]
