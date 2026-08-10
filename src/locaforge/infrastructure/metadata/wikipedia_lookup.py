"""Small Wikipedia search adapter used for project-profile hints."""

from __future__ import annotations

import html
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class WikipediaProjectMetadataLookup:
    _ENDPOINT = "https://en.wikipedia.org/w/api.php"

    def lookup(self, project_name: str) -> str:
        name = project_name.strip()
        if not name:
            raise ValueError("Project name must not be empty")
        query = urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": name,
                "srlimit": 3,
                "srprop": "snippet",
                "format": "json",
                "formatversion": 2,
            }
        )
        request = Request(
            f"{self._ENDPOINT}?{query}",
            headers={"User-Agent": "LocaForge/1.0 project metadata lookup"},
        )
        with urlopen(request, timeout=10.0) as response:  # noqa: S310
            body = json.loads(response.read().decode("utf-8"))
        search = body.get("query", {}).get("search", []) if isinstance(body, dict) else []
        if not isinstance(search, list):
            return ""
        lines: list[str] = []
        for result in search:
            if not isinstance(result, dict):
                continue
            title = result.get("title")
            snippet = result.get("snippet")
            if isinstance(title, str) and isinstance(snippet, str):
                plain_snippet = html.unescape(re.sub(r"<[^>]+>", "", snippet))
                lines.append(f"{title}: {plain_snippet.strip()}")
        return "\n".join(lines)[:4_000]
