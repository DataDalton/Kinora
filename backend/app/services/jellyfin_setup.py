"""
Links Kinora to the Jellyfin bundled by docker-compose.jellyfin.yml.

That compose file's bootstrap writes a generated admin password into the secrets volume,
and the file's presence is what marks Jellyfin as bundled. While no Jellyfin API key is
saved, Kinora waits for Jellyfin to answer, completes its first-run wizard with the
generated admin login, signs in once to create a Kinora API key and one library per root
folder, then saves the URL and key and turns on library updates. Jellyfin and Kinora mount
the media folder at the same path, so no path mappings are needed.

A Jellyfin whose wizard was completed by hand, with a different admin login, is left
alone, and the settings page keeps its manual form. Nothing here blocks startup.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services import jellyfin

logger = logging.getLogger(__name__)

# Address of the bundled Jellyfin on the compose network, and the port it is published on.
BUNDLED_URL = "http://jellyfin:8096"
BUNDLED_PORT = 8096
ADMIN_USERNAME = "kinora"
# Secrets volume file written by the bootstrap in docker-compose.jellyfin.yml.
ADMIN_PASSWORD_SECRET = "jellyfin_admin_password"
API_KEY_APP_NAME = "Kinora"

# Jellyfin library type for each Kinora root folder media type.
COLLECTION_TYPES = {"movies": "movies", "shows": "tvshows", "anime": "tvshows", "music": "music"}

# Jellyfin can take a while to start on first boot, so linking keeps retrying.
RETRY_SECONDS = 10
RETRY_LIMIT = 90

# Dragonfly key holding the latest linking state for the settings page.
STATUS_KEY = "jellyfin:setup_status"

# Advisory lock so only one API process links at a time.
LINK_LOCK_ID = 4915625

_CLIENT_HEADER = 'MediaBrowser Client="Kinora", Device="Kinora", DeviceId="kinora-setup", Version="1.0.0"'


def adminPassword() -> Optional[str]:
    """The generated admin password, or None when this install does not bundle Jellyfin."""
    return settings._read_secret_file(ADMIN_PASSWORD_SECRET)


def isBundled() -> bool:
    return adminPassword() is not None


def _recordStatus(state: str, message: str) -> None:
    try:
        jellyfin._getSyncRedis().set(STATUS_KEY, json.dumps({"state": state, "message": message}))
    except Exception as e:
        logger.debug("Could not store the Jellyfin setup status: %s", e)


def readStatus() -> Optional[Dict[str, str]]:
    """The latest linking state and message, or None before linking has run."""
    try:
        raw = jellyfin._getSyncRedis().get(STATUS_KEY)
        return json.loads(raw) if raw else None
    except Exception:
        return None


class _SetupError(Exception):
    pass


async def _call(method: str, path: str, token: Optional[str] = None, body: Any = None, params: Any = None):
    from app.core.http_client import http_request

    header = _CLIENT_HEADER + (f', Token="{token}"' if token else "")
    kwargs: Dict[str, Any] = {
        "headers": {"Authorization": header, "Accept": "application/json"},
        "timeout": jellyfin.REQUEST_TIMEOUT_SECONDS,
    }
    if body is not None:
        kwargs["json"] = body
    if params is not None:
        kwargs["params"] = params
    response = await http_request(method, f"{BUNDLED_URL}{path}", **kwargs)
    if response.status_code >= 400:
        raise _SetupError(f"Jellyfin answered HTTP {response.status_code} to {method} {path}")
    return response


async def _completeWizard(password: str) -> None:
    """Run Jellyfin's first-run wizard, creating the admin account."""
    await _call(
        "POST",
        "/Startup/Configuration",
        body={"UICulture": "en-US", "MetadataCountryCode": "US", "PreferredMetadataLanguage": "en"},
    )
    # Jellyfin creates its default admin when this is read, and renames that account below.
    await _call("GET", "/Startup/User")
    await _call("POST", "/Startup/User", body={"Name": ADMIN_USERNAME, "Password": password})
    await _call("POST", "/Startup/RemoteAccess", body={"EnableRemoteAccess": True})
    await _call("POST", "/Startup/Complete")


async def _signIn(password: str) -> Optional[str]:
    """An access token for the admin account, or None when Jellyfin refuses the login."""
    try:
        response = await _call("POST", "/Users/AuthenticateByName", body={"Username": ADMIN_USERNAME, "Pw": password})
    except _SetupError:
        return None
    return (response.json() or {}).get("AccessToken")


async def _apiKey(token: str) -> str:
    """The Kinora API key, created when Jellyfin does not have one yet."""

    async def existing() -> Optional[str]:
        items = (await _call("GET", "/Auth/Keys", token)).json().get("Items") or []
        return next((item["AccessToken"] for item in items if item.get("AppName") == API_KEY_APP_NAME), None)

    key = await existing()
    if not key:
        await _call("POST", "/Auth/Keys", token, params={"app": API_KEY_APP_NAME})
        key = await existing()
    if not key:
        raise _SetupError("Jellyfin did not return the new API key")
    return key


async def _libraries(token: str) -> List[Dict[str, Any]]:
    return (await _call("GET", "/Library/VirtualFolders", token)).json() or []


async def _ensureLibrary(token: str, folder: Dict[str, Any], libraries: List[Dict[str, Any]], refresh: bool) -> bool:
    """
    Make a root folder's path part of a Jellyfin library. A library already holding the
    path is left as is. A library with the folder's name and type gets the path added,
    so a second Movies folder joins the Movies library. Otherwise a library is created,
    numbered when the name is taken by a library of another type. Returns True on a change.
    """
    collectionType = COLLECTION_TYPES.get(folder["media_type"])
    path = folder["root_path"]
    if not collectionType or any(path in (library.get("Locations") or []) for library in libraries):
        return False
    refreshValue = "true" if refresh else "false"
    sameName = next((library for library in libraries if library.get("Name") == folder["name"]), None)
    if sameName and sameName.get("CollectionType") == collectionType:
        await _call(
            "POST",
            "/Library/VirtualFolders/Paths",
            token,
            body={"Name": sameName["Name"], "PathInfo": {"Path": path}},
            params={"refreshLibrary": refreshValue},
        )
        sameName.setdefault("Locations", []).append(path)
        return True
    name = folder["name"]
    takenNames = {library.get("Name") for library in libraries}
    number = 2
    while name in takenNames:
        name = f"{folder['name']} {number}"
        number += 1
    await _call(
        "POST",
        "/Library/VirtualFolders",
        token,
        body={"LibraryOptions": {"PathInfos": [{"Path": path}]}},
        params={"name": name, "collectionType": collectionType, "refreshLibrary": refreshValue},
    )
    libraries.append({"Name": name, "CollectionType": collectionType, "Locations": [path]})
    return True


async def _createLibraries(conn, token: str) -> List[str]:
    """A library for every active root folder no library covers yet. Returns the folder names added."""
    folders = await conn.fetch(
        "SELECT media_type, name, root_path FROM root_folders WHERE is_active ORDER BY priority, id"
    )
    libraries = await _libraries(token)
    created = [folder["name"] for folder in folders if await _ensureLibrary(token, dict(folder), libraries, False)]
    if created:
        await _call("POST", "/Library/Refresh", token)
    return created


async def _saveLink(conn, apiKey: str) -> None:
    from app.api.v1.endpoints.settings import encrypt_value

    rows = [
        (jellyfin.SETTING_ENABLED, "true", "boolean", False, "Send library changes to Jellyfin"),
        (jellyfin.SETTING_URL, BUNDLED_URL, "string", False, "Jellyfin server URL"),
        (jellyfin.SETTING_API_KEY, encrypt_value(apiKey), "string", True, "Jellyfin API key"),
        (jellyfin.SETTING_PATH_MAPPINGS, "[]", "json", False, "Kinora to Jellyfin path prefixes"),
    ]
    for key, value, valueType, encrypted, description in rows:
        await conn.execute(
            "INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description) "
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
            key,
            value,
            valueType,
            encrypted,
            jellyfin.SETTINGS_CATEGORY,
            description,
        )


def isLinkedToBundled(config: Dict[str, Any]) -> bool:
    """True when Kinora's saved Jellyfin is the bundled one, which sees the same paths."""
    return bool(config.get("apiKey")) and config.get("url") == BUNDLED_URL


async def syncFolderLibrary(old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]]) -> None:
    """
    Carry one root folder change over to the bundled Jellyfin. old is the folder before the
    change and new after it, each a dict with name, root_path and media_type, None for a
    folder created or deleted. A deleted folder's path leaves its library, and a library
    left with no paths is removed. Media files are never touched, only Jellyfin's library
    list. Does nothing unless Kinora is linked to the bundled Jellyfin, and never raises.
    """
    try:
        config = await jellyfin.loadConfig()
        if not isLinkedToBundled(config):
            return
        token = config["apiKey"]
        libraries = await _libraries(token)
        oldPath = old["root_path"] if old else None
        newPath = new["root_path"] if new else None
        holder = next((library for library in libraries if oldPath in (library.get("Locations") or [])), None)

        if holder and oldPath != newPath:
            if len(holder.get("Locations") or []) <= 1 and new is None:
                await _call(
                    "DELETE",
                    "/Library/VirtualFolders",
                    token,
                    params={"name": holder["Name"], "refreshLibrary": "true"},
                )
                libraries.remove(holder)
            else:
                if new is not None and COLLECTION_TYPES.get(new["media_type"]) == holder.get("CollectionType"):
                    # A moved folder keeps its library, with the new path added before the old one goes.
                    await _call(
                        "POST",
                        "/Library/VirtualFolders/Paths",
                        token,
                        body={"Name": holder["Name"], "PathInfo": {"Path": newPath}},
                        params={"refreshLibrary": "false"},
                    )
                    holder["Locations"].append(newPath)
                await _call(
                    "DELETE",
                    "/Library/VirtualFolders/Paths",
                    token,
                    params={"name": holder["Name"], "path": oldPath, "refreshLibrary": "true"},
                )
                holder["Locations"].remove(oldPath)

        if new is not None:
            # A renamed folder renames the library it alone fills.
            current = next((library for library in libraries if newPath in (library.get("Locations") or [])), None)
            if (
                current
                and old is not None
                and old["name"] != new["name"]
                and current.get("Name") == old["name"]
                and current.get("Locations") == [newPath]
                and new["name"] not in {library.get("Name") for library in libraries}
            ):
                await _call(
                    "POST",
                    "/Library/VirtualFolders/Name",
                    token,
                    params={"name": current["Name"], "newName": new["name"], "refreshLibrary": "false"},
                )
            await _ensureLibrary(token, new, libraries, True)
    except Exception as e:
        logger.warning("Could not update the Jellyfin libraries for a root folder change: %s", e)


async def linkBundledJellyfin() -> bool:
    """
    One linking attempt. Returns True once settled (linked, not bundled, or set up by hand)
    and False while Jellyfin is not answering yet.
    """
    password = adminPassword()
    if not password:
        return True

    from app.db import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", LINK_LOCK_ID)
            if (await jellyfin.loadConfig(conn))["apiKey"]:
                return True

            try:
                info = (await _call("GET", "/System/Info/Public")).json() or {}
            except Exception:
                _recordStatus("waiting", "Waiting for Jellyfin to start")
                return False

            try:
                if not info.get("StartupWizardCompleted"):
                    await _completeWizard(password)
                    print("[INIT] Completed the Jellyfin setup wizard")
                token = await _signIn(password)
                if not token:
                    _recordStatus(
                        "manual",
                        "Jellyfin was set up by hand, so Kinora did not link it. Enter an API key below.",
                    )
                    return True
                apiKey = await _apiKey(token)
                created = await _createLibraries(conn, token)
                await _saveLink(conn, apiKey)
                try:
                    await _call("POST", "/Sessions/Logout", token)
                except Exception:
                    pass
            except Exception as e:
                _recordStatus("error", f"Linking Jellyfin failed. {e}")
                print(f"[INIT] Jellyfin linking failed: {e}")
                return False

    libraries = f", created libraries {', '.join(created)}" if created else ""
    _recordStatus("linked", "Linked automatically")
    print(f"[INIT] Linked the bundled Jellyfin{libraries}")
    return True


async def linkBundledJellyfinWhenReady() -> None:
    """Keep attempting the link until Jellyfin answers or the window closes."""
    if not isBundled():
        return
    for _ in range(RETRY_LIMIT):
        if await linkBundledJellyfin():
            return
        await asyncio.sleep(RETRY_SECONDS)
    print("[INIT] Jellyfin never answered, linking skipped until the next start")
