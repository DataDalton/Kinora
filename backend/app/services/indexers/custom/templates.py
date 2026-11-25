"""
Example definitions shown in the indexer editor as starting points.

These are documentation, not indexers. Nothing here is searched until an administrator
copies one into a new indexer, points it at a real site and saves it. The sites named
are placeholders.
"""

from typing import Any, Dict, List

JSON_API_EXAMPLE: Dict[str, Any] = {
    "format": "kinora-indexer/1",
    "name": "Example JSON tracker",
    "description": "A tracker with a JSON search API authenticated by an API key header",
    "baseUrl": "https://tracker.example",
    "credentials": [{"key": "apiKey", "label": "API key"}],
    "login": {
        "method": "header",
        "header": {"name": "Authorization", "value": "Bearer {apiKey}"},
        "check": {"path": "/api/user", "contains": "username"},
    },
    "search": {
        "path": "/api/torrents",
        "method": "GET",
        "params": {"q": "{query}", "imdb": "{imdbId}", "season": "{season}", "category": "{category}"},
        "response": "json",
        "rows": "data[*]",
        "fields": {
            "title": {"path": "name"},
            "download": {"path": "id", "template": "/api/torrents/{value}/download"},
            "infohash": {"path": "info_hash"},
            "size": {"path": "size"},
            "seeders": {"path": "seeders"},
            "leechers": {"path": "leechers"},
            "publishDate": {"path": "created_at"},
            "uploader": {"path": "uploader.name"},
            "details": {"path": "id", "template": "/torrents/{value}"},
        },
    },
    "categories": {"movies": ["1"], "shows": ["2"], "anime": ["4"], "music": ["3"]},
}

HTML_FORM_EXAMPLE: Dict[str, Any] = {
    "format": "kinora-indexer/1",
    "name": "Example HTML tracker",
    "description": "A tracker with an HTML browse page and a username and password login form",
    "baseUrl": "https://forum-tracker.example",
    "credentials": [
        {"key": "username", "label": "Username"},
        {"key": "password", "label": "Password"},
    ],
    "login": {
        "method": "form",
        "form": {
            "path": "/login.php",
            "fields": {"username": "{username}", "password": "{password}", "keeplogged": "1"},
            "success": {"notContains": "Invalid username or password"},
        },
        "check": {"path": "/index.php", "contains": "logout.php"},
    },
    "search": {
        "path": "/browse.php",
        "method": "GET",
        "params": {"search": "{query}", "cat": "{category}"},
        "response": "html",
        "rows": "table#torrent_table tr.torrent",
        "fields": {
            "title": {"selector": "a.torrent-name", "attribute": "text"},
            "download": {"selector": "a[href*='download.php']", "attribute": "href"},
            "details": {"selector": "a.torrent-name", "attribute": "href"},
            "size": {"selector": "td.size", "attribute": "text"},
            "seeders": {"selector": "td.seeders", "attribute": "text"},
            "leechers": {"selector": "td.leechers", "attribute": "text"},
            "publishDate": {"selector": "td.added span", "attribute": "title", "dateFormat": "%Y-%m-%d %H:%M:%S"},
            "uploader": {"selector": "td.uploader a", "attribute": "text", "default": "Anonymous"},
        },
    },
    "categories": {"movies": ["1", "2"], "shows": ["5"], "music": ["7"]},
}

TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "json-api",
        "label": "JSON API with an API key",
        "description": JSON_API_EXAMPLE["description"],
        "definition": JSON_API_EXAMPLE,
    },
    {
        "id": "html-form",
        "label": "HTML pages with a login form",
        "description": HTML_FORM_EXAMPLE["description"],
        "definition": HTML_FORM_EXAMPLE,
    },
]
