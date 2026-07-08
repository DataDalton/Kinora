"""
NFO writer.

Generates Kodi/Jellyfin-compatible movie.nfo and tvshow.nfo files from stored metadata.
Only written when a profile uses the Jellyfin media-server preset.
"""

import os
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape


def _genre_names(genres: Any) -> List[str]:
    if not genres:
        return []
    names = []
    for g in genres:
        if isinstance(g, dict):
            name = g.get("name")
        else:
            name = g
        if name:
            names.append(str(name))
    return names


def _year_of(value) -> Optional[str]:
    if not value:
        return None
    if hasattr(value, "year"):
        return str(value.year)
    return str(value)[:4]


def _write(folder: str, filename: str, xml: str) -> bool:
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, filename), "w", encoding="utf-8") as f:
            f.write(xml)
        return True
    except OSError:
        return False


def write_movie_nfo(folder: str, row: Dict[str, Any]) -> bool:
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', "<movie>"]
    if row.get("title"):
        lines.append(f"  <title>{escape(str(row['title']))}</title>")
    year = _year_of(row.get("release_date"))
    if year:
        lines.append(f"  <year>{year}</year>")
    if row.get("overview"):
        lines.append(f"  <plot>{escape(str(row['overview']))}</plot>")
    for name in _genre_names(row.get("genres")):
        lines.append(f"  <genre>{escape(name)}</genre>")
    if row.get("tmdb_id"):
        lines.append(f'  <uniqueid type="tmdb" default="true">{row["tmdb_id"]}</uniqueid>')
    if row.get("imdb_id"):
        lines.append(f'  <uniqueid type="imdb">{escape(str(row["imdb_id"]))}</uniqueid>')
    lines.append("</movie>")
    return _write(folder, "movie.nfo", "\n".join(lines))


def write_tvshow_nfo(folder: str, row: Dict[str, Any]) -> bool:
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', "<tvshow>"]
    if row.get("title"):
        lines.append(f"  <title>{escape(str(row['title']))}</title>")
    year = _year_of(row.get("first_air_date") or row.get("release_date"))
    if year:
        lines.append(f"  <year>{year}</year>")
    if row.get("overview"):
        lines.append(f"  <plot>{escape(str(row['overview']))}</plot>")
    for name in _genre_names(row.get("genres")):
        lines.append(f"  <genre>{escape(name)}</genre>")
    if row.get("tmdb_id"):
        lines.append(f'  <uniqueid type="tmdb" default="true">{row["tmdb_id"]}</uniqueid>')
    if row.get("tvdb_id"):
        lines.append(f'  <uniqueid type="tvdb">{row["tvdb_id"]}</uniqueid>')
    lines.append("</tvshow>")
    return _write(folder, "tvshow.nfo", "\n".join(lines))
