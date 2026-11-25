"""
Kinora indexer definitions.

A definition describes a site that has no dedicated adapter, in JSON:

    format        "kinora-indexer/1"
    name          display name, optional
    description   optional
    baseUrl       suggested base URL, optional. The indexer's own base URL wins
    credentials   secret fields the user fills in, as ["apiKey"] or
                  [{"key": "apiKey", "label": "API key"}]
    login         how requests are authenticated
        method    none, header, query, cookie or form
        header    {"name": "Authorization", "value": "Bearer {apiKey}"}       for header
        query     {"name": "apikey", "value": "{apiKey}"}                     for query
        cookie    {"value": "{cookie}"}                                       for cookie
        form      {"path": "/login.php", "fields": {"username": "{username}",
                   "password": "{password}"}, "success": {"cookie": "session"}}
                  success takes cookie (a cookie that must be set), contains or
                  notContains (text the answer must or must not hold)
        check     {"path": "/index.php", "contains": "logout"}, optional. Used by the
                  test, and for form logins to notice an expired session
    search        how a search is requested and read
        path      URL path, may hold variables
        method    GET or POST
        params    query or form parameters. A parameter whose value is empty after
                  variables are filled in is left out
        response  json or html
        rows      json: dotted path to the result list, such as "data.torrents[*]"
                  html: CSS selector of the result rows, such as "table.torrents tr"
        rowsSkip  rows to skip at the start, such as a header row
        fields    how each result field is read, see below
    rss           optional, same shape as search without query variables. Without it
                  the RSS monitor runs search with an empty query
    categories    category ids per media type, {"movies": ["1"], "shows": ["5"]}

Variables, written {name}: query, imdbId (with tt), imdbNumeric, tmdbId, tvdbId,
season, episode, category (the scope's ids joined by commas), artist, album, year,
baseUrl, and every credential key.

Fields are title, download, magnet, infohash, size, seeders, leechers, publishDate,
uploader and details. title and at least one of download, magnet or infohash are
required. Each field is read with one of

    path        json: dotted path inside the row, such as "attributes.name" or "files[0]"
    selector    html: CSS selector inside the row
    attribute   html: attribute to read, such as "href" or "title". Default is the text
    value       a fixed value, which may use variables

and then optionally changed by

    regex       first capture group of a regular expression, or the whole match
    template    text with {value} replaced by what was read, such as "/download/{value}"
    dateFormat  strptime pattern for publishDate when it is not ISO, RFC 822 or a timestamp
    default     used when nothing was read

The HTML parser is BeautifulSoup, which the built-in indexers already use.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from bs4 import BeautifulSoup

from app.services.indexers.base import TorrentRelease
from app.services.indexers.custom.common import CustomIndexer, FieldSpec, IndexerError, parseDate, toInt

FORMAT_ID = "kinora-indexer/1"
LOGIN_METHODS = ("none", "header", "query", "cookie", "form")
RESPONSE_TYPES = ("json", "html")
FIELD_NAMES = (
    "title",
    "download",
    "magnet",
    "infohash",
    "size",
    "seeders",
    "leechers",
    "publishDate",
    "uploader",
    "details",
)
SOURCE_KEYS = ("path", "selector", "value")
FIELD_KEYS = {"path", "selector", "attribute", "value", "regex", "template", "dateFormat", "default"}
SEARCH_VARIABLES = {
    "query",
    "imdbId",
    "imdbNumeric",
    "tmdbId",
    "tvdbId",
    "season",
    "episode",
    "category",
    "artist",
    "album",
    "year",
    "baseUrl",
}
SCOPES = ("movies", "shows", "anime", "music")
_VARIABLE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_PATH_PART = re.compile(r"^([^\[\]]*)((?:\[(?:\d+|\*)\])*)$")


class DefinitionError(ValueError):
    """A definition that failed validation, with one message per problem."""

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def credentialKeys(definition: Dict[str, Any]) -> List[str]:
    keys = []
    for entry in definition.get("credentials") or []:
        key = entry.get("key") if isinstance(entry, dict) else entry
        if isinstance(key, str) and key:
            keys.append(key)
    return keys


def credentialLabels(definition: Dict[str, Any]) -> List[Tuple[str, str]]:
    labels = []
    for entry in definition.get("credentials") or []:
        if isinstance(entry, dict) and entry.get("key"):
            labels.append((entry["key"], str(entry.get("label") or entry["key"])))
        elif isinstance(entry, str) and entry:
            labels.append((entry, entry))
    return labels


def parseDefinitionText(text: str) -> Dict[str, Any]:
    """A definition from JSON text, raising DefinitionError with the line and column of a syntax error."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError as e:
        raise DefinitionError([f"Not valid JSON at line {e.lineno}, column {e.colno}: {e.msg}"])
    if not isinstance(value, dict):
        raise DefinitionError(["The definition must be a JSON object"])
    return value


def _checkTemplate(text: Any, where: str, allowed: set, errors: List[str]) -> None:
    if not isinstance(text, str):
        errors.append(f"{where} must be text")
        return
    for name in _VARIABLE.findall(text):
        if name not in allowed:
            errors.append(f"{where} uses unknown variable {{{name}}}")


def _checkPath(path: Any, where: str, allowStar: bool, errors: List[str]) -> None:
    if not isinstance(path, str) or not path.strip():
        errors.append(f"{where} must be a non-empty dotted path")
        return
    for part in path.removeprefix("$.").removeprefix("$").split("."):
        if part == "" and path not in ("$", ""):
            errors.append(f"{where} has an empty segment in '{path}'")
            return
        if not _PATH_PART.match(part):
            errors.append(f"{where} has an unreadable segment '{part}'")
            return
        if "[*]" in part and not allowStar:
            errors.append(f"{where} may not use [*]. Only rows can")
            return


def _checkSelector(selector: Any, where: str, errors: List[str]) -> None:
    if not isinstance(selector, str) or not selector.strip():
        errors.append(f"{where} must be a non-empty CSS selector")
        return
    try:
        BeautifulSoup("<div></div>", "html.parser").select(selector)
    except Exception as e:
        errors.append(f"{where} is not a valid CSS selector ({e})")


def _checkRequest(section: Any, where: str, allowed: set, errors: List[str]) -> None:
    if not isinstance(section, dict):
        errors.append(f"{where} must be an object")
        return
    if "path" not in section:
        errors.append(f"{where}.path is required")
    else:
        _checkTemplate(section["path"], f"{where}.path", allowed, errors)
    method = str(section.get("method") or "GET").upper()
    if method not in ("GET", "POST"):
        errors.append(f"{where}.method must be GET or POST")
    params = section.get("params")
    if params is not None:
        if not isinstance(params, dict):
            errors.append(f"{where}.params must be an object")
        else:
            for key, value in params.items():
                _checkTemplate(
                    str(value) if isinstance(value, (int, float)) else value, f"{where}.params.{key}", allowed, errors
                )
    response = section.get("response")
    if response not in RESPONSE_TYPES:
        errors.append(f"{where}.response must be json or html")
        return
    rows = section.get("rows")
    if response == "json":
        _checkPath(rows, f"{where}.rows", True, errors)
    else:
        _checkSelector(rows, f"{where}.rows", errors)
    skip = section.get("rowsSkip", 0)
    if not isinstance(skip, int) or skip < 0:
        errors.append(f"{where}.rowsSkip must be a whole number of zero or more")
    fields = section.get("fields")
    if not isinstance(fields, dict):
        errors.append(f"{where}.fields must be an object")
        return
    for name in fields:
        if name not in FIELD_NAMES:
            errors.append(f"{where}.fields.{name} is not a known field. Known fields are {', '.join(FIELD_NAMES)}")
    if "title" not in fields:
        errors.append(f"{where}.fields.title is required")
    if not any(name in fields for name in ("download", "magnet", "infohash")):
        errors.append(f"{where}.fields needs download, magnet or infohash")
    for name, spec in fields.items():
        fieldWhere = f"{where}.fields.{name}"
        if not isinstance(spec, dict):
            errors.append(f"{fieldWhere} must be an object")
            continue
        unknown = set(spec) - FIELD_KEYS
        if unknown:
            errors.append(f"{fieldWhere} has unknown keys {', '.join(sorted(unknown))}")
        sources = [key for key in SOURCE_KEYS if key in spec]
        if len(sources) != 1:
            errors.append(f"{fieldWhere} needs exactly one of path, selector or value")
            continue
        if "path" in spec:
            if response != "json":
                errors.append(f"{fieldWhere}.path only works with json responses. Use selector for html")
            _checkPath(spec["path"], f"{fieldWhere}.path", False, errors)
        if "selector" in spec:
            if response != "html":
                errors.append(f"{fieldWhere}.selector only works with html responses. Use path for json")
            _checkSelector(spec["selector"], f"{fieldWhere}.selector", errors)
        if "value" in spec:
            _checkTemplate(str(spec["value"]), f"{fieldWhere}.value", allowed, errors)
        if "regex" in spec:
            try:
                re.compile(spec["regex"])
            except (re.error, TypeError) as e:
                errors.append(f"{fieldWhere}.regex is not a valid regular expression ({e})")
        if "template" in spec:
            if not isinstance(spec["template"], str) or "{value}" not in spec["template"]:
                errors.append(f"{fieldWhere}.template must be text containing {{value}}")
        if "attribute" in spec and not isinstance(spec["attribute"], str):
            errors.append(f"{fieldWhere}.attribute must be text")
        if "dateFormat" in spec and name != "publishDate":
            errors.append(f"{fieldWhere}.dateFormat only applies to publishDate")


def validateDefinition(definition: Any) -> List[str]:
    """Every problem with a definition, as messages naming the key at fault. Empty when it is valid."""
    errors: List[str] = []
    if not isinstance(definition, dict):
        return ["The definition must be a JSON object"]
    if definition.get("format") != FORMAT_ID:
        errors.append(f'format must be "{FORMAT_ID}"')
    credentials = definition.get("credentials", [])
    if not isinstance(credentials, list):
        errors.append("credentials must be a list")
    else:
        for position, entry in enumerate(credentials):
            key = entry.get("key") if isinstance(entry, dict) else entry
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key or ""):
                errors.append(f"credentials[{position}] needs a key made of letters, digits and underscores")
            elif key in SEARCH_VARIABLES or key == "value":
                errors.append(f"credentials[{position}] key '{key}' is reserved for a search variable")
    allowed = SEARCH_VARIABLES | set(credentialKeys(definition))

    login = definition.get("login") or {"method": "none"}
    if not isinstance(login, dict):
        errors.append("login must be an object")
        login = {"method": "none"}
    method = login.get("method", "none")
    if method not in LOGIN_METHODS:
        errors.append(f"login.method must be one of {', '.join(LOGIN_METHODS)}")
    elif method in ("header", "query"):
        part = login.get(method)
        if not isinstance(part, dict) or not part.get("name") or "value" not in part:
            errors.append(f"login.{method} needs name and value")
        else:
            _checkTemplate(part["value"], f"login.{method}.value", allowed, errors)
    elif method == "cookie":
        part = login.get("cookie")
        if not isinstance(part, dict) or "value" not in part:
            errors.append("login.cookie needs value, such as {cookie}")
        else:
            _checkTemplate(part["value"], "login.cookie.value", allowed, errors)
    elif method == "form":
        form = login.get("form")
        if not isinstance(form, dict):
            errors.append("login.form must be an object")
        else:
            if not form.get("path"):
                errors.append("login.form.path is required")
            fields = form.get("fields")
            if not isinstance(fields, dict) or not fields:
                errors.append("login.form.fields must list the form fields")
            else:
                for key, value in fields.items():
                    _checkTemplate(str(value), f"login.form.fields.{key}", allowed, errors)
            success = form.get("success")
            if not isinstance(success, dict) or not any(k in success for k in ("cookie", "contains", "notContains")):
                errors.append("login.form.success needs cookie, contains or notContains")
    check = login.get("check")
    if check is not None:
        if not isinstance(check, dict) or not check.get("path") or not check.get("contains"):
            errors.append("login.check needs path and contains")

    if "search" not in definition:
        errors.append("search is required")
    else:
        _checkRequest(definition["search"], "search", allowed, errors)
    if definition.get("rss") is not None:
        _checkRequest(definition["rss"], "rss", allowed - {"query"}, errors)

    categories = definition.get("categories")
    if categories is not None:
        if not isinstance(categories, dict):
            errors.append("categories must be an object")
        else:
            for scope, ids in categories.items():
                if scope not in SCOPES:
                    errors.append(f"categories.{scope} is not a media type. Use {', '.join(SCOPES)}")
                elif not isinstance(ids, list):
                    errors.append(f"categories.{scope} must be a list of ids")
    return errors


# ---------------------------------------------------------------------------
# Reading results
# ---------------------------------------------------------------------------


def _walk(value: Any, path: str) -> List[Any]:
    """Every value a dotted path reaches. [*] fans out over a list."""
    current = [value]
    for part in path.removeprefix("$.").removeprefix("$").split("."):
        if part == "":
            continue
        match = _PATH_PART.match(part)
        if not match:
            return []
        key, indexes = match.group(1), match.group(2)
        nextValues = []
        for item in current:
            if key:
                if not isinstance(item, dict) or key not in item:
                    continue
                item = item[key]
            results = [item]
            for index in re.findall(r"\[(\d+|\*)\]", indexes):
                expanded = []
                for entry in results:
                    if not isinstance(entry, list):
                        continue
                    if index == "*":
                        expanded.extend(entry)
                    elif int(index) < len(entry):
                        expanded.append(entry[int(index)])
                results = expanded
            nextValues.extend(results)
        current = nextValues
    return current


def fillTemplate(text: str, variables: Dict[str, Any], encode: bool) -> str:
    def replace(match):
        value = variables.get(match.group(1))
        if value is None:
            return ""
        value = str(value)
        return quote(value, safe="") if encode else value

    return _VARIABLE.sub(replace, text)


def readRows(section: Dict[str, Any], body: str) -> List[Any]:
    """The result rows of an answer. Raises IndexerError(stage parse) when the answer cannot be read."""
    skip = int(section.get("rowsSkip") or 0)
    if section["response"] == "json":
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            snippet = " ".join((body or "")[:120].split())
            raise IndexerError(
                f"The answer is not JSON ({e.msg}). It starts with: {snippet or 'nothing'}",
                stage="parse",
                field="rows",
            )
        found = _walk(payload, section["rows"])
        if section["rows"].rstrip().endswith("[*]"):
            rows = found
        elif len(found) == 1 and isinstance(found[0], list):
            rows = found[0]
        elif not found:
            raise IndexerError(
                f"rows path '{section['rows']}' matched nothing in the answer", stage="parse", field="rows"
            )
        else:
            rows = found
        return rows[skip:]
    soup = BeautifulSoup(body or "", "html.parser")
    return soup.select(section["rows"])[skip:]


def _readRaw(spec: Dict[str, Any], row: Any, variables: Dict[str, Any]) -> Optional[str]:
    if "value" in spec:
        return fillTemplate(str(spec["value"]), variables, encode=False)
    if "path" in spec:
        values = _walk(row, spec["path"])
        if not values or values[0] is None:
            return None
        value = values[0]
        return json.dumps(value) if isinstance(value, (dict, list)) else str(value)
    element = row.select_one(spec["selector"]) if hasattr(row, "select_one") else None
    if element is None:
        return None
    attribute = spec.get("attribute") or "text"
    if attribute == "text":
        return element.get_text(" ", strip=True)
    value = element.get(attribute)
    if isinstance(value, list):
        value = " ".join(value)
    return value


def readField(name: str, spec: Dict[str, Any], row: Any, variables: Dict[str, Any]) -> Optional[str]:
    raw = _readRaw(spec, row, variables)
    if raw is not None and "regex" in spec:
        match = re.search(spec["regex"], raw)
        raw = (match.group(1) if match.groups() else match.group(0)) if match else None
    if raw is not None and "template" in spec:
        raw = spec["template"].replace("{value}", raw)
    if (raw is None or str(raw).strip() == "") and "default" in spec:
        raw = str(spec["default"])
    return raw.strip() if isinstance(raw, str) else raw


class DefinitionIndexer(CustomIndexer):
    kind = "definition"
    label = "Kinora definition"
    description = "Any other site, described by a JSON definition"
    supportsRss = True

    @classmethod
    def validateConfig(cls, baseUrl, settings, credentials, definition) -> List[str]:
        errors = []
        if not (baseUrl or "").lower().startswith(("http://", "https://")):
            errors.append("Base URL must start with http:// or https://")
        definitionErrors = validateDefinition(definition)
        errors.extend(f"Definition: {message}" for message in definitionErrors)
        if not definitionErrors:
            for key, label in credentialLabels(definition):
                if not str(credentials.get(key) or "").strip():
                    errors.append(f"{label} is required by the definition")
        return errors

    def __init__(self, config):
        super().__init__(config)
        self.definition = config.definition or {}
        self.login = self.definition.get("login") or {"method": "none"}
        self._session = None
        self._loggedIn = False

    def categoryIds(self, scope: str) -> List[str]:
        configured = (self.config.settings.get("categories") or {}).get(scope)
        if configured is None:
            configured = (self.definition.get("categories") or {}).get(scope, [])
        return [str(c).strip() for c in configured or [] if str(c).strip()]

    def _variables(self, query: str, scope: str, context) -> Dict[str, Any]:
        variables: Dict[str, Any] = dict(self.config.credentials)
        variables.update(
            {
                "query": query or "",
                "baseUrl": self.base_url,
                "category": ",".join(self.categoryIds(scope)),
            }
        )
        if context is not None:
            variables.update(
                {
                    "imdbId": context.imdbId,
                    "imdbNumeric": context.imdbNumeric,
                    "tmdbId": context.tmdbId,
                    "tvdbId": context.tvdbId,
                    "season": context.season,
                    "episode": context.episode if context.singleEpisode else None,
                    "artist": context.artist,
                    "album": context.album,
                    "year": context.year,
                }
            )
        return variables

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def authHeaders(self) -> Dict[str, str]:
        if self.login.get("method") != "header":
            return {}
        part = self.login["header"]
        return {part["name"]: fillTemplate(str(part["value"]), self.config.credentials, encode=False)}

    def authParams(self) -> Dict[str, str]:
        if self.login.get("method") != "query":
            return {}
        part = self.login["query"]
        return {part["name"]: fillTemplate(str(part["value"]), self.config.credentials, encode=False)}

    def authCookies(self) -> Dict[str, str]:
        if self.login.get("method") != "cookie":
            return {}
        raw = fillTemplate(str(self.login["cookie"]["value"]), self.config.credentials, encode=False)
        cookies = {}
        for part in raw.split(";"):
            name, _, value = part.strip().partition("=")
            if name and value:
                cookies[name] = value
        return cookies

    async def httpSession(self):
        """A session with its own cookie jar for form logins, so the login cookies stay with this indexer."""
        if self.login.get("method") != "form":
            return await super().httpSession()
        if self._session is None:
            from curl_cffi.requests import AsyncSession

            self._session = AsyncSession(timeout=30.0, allow_redirects=True, max_redirects=10)
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    async def _formLogin(self) -> None:
        form = self.login["form"]
        fields = {
            key: fillTemplate(str(value), self.config.credentials, encode=False)
            for key, value in form["fields"].items()
        }
        response = await self.request(
            "POST", self.absoluteUrl(form["path"]), data=fields, withAuth=False, allowStatus=(401, 403)
        )
        success = form.get("success") or {}
        body = response.text or ""
        failed = response.status_code in (401, 403)
        if not failed and success.get("cookie"):
            session = await self.httpSession()
            failed = success["cookie"] not in {cookie.name for cookie in session.cookies.jar}
        if not failed and success.get("contains"):
            failed = success["contains"] not in body
        if not failed and success.get("notContains"):
            failed = success["notContains"] in body
        if failed:
            self._loggedIn = False
            raise IndexerError(f"Login to {self.name} failed. The success check did not pass", stage="auth")
        self._loggedIn = True

    def _sessionExpired(self, response) -> bool:
        if response.status_code in (401, 403):
            return True
        form = self.login.get("form") or {}
        loginPath = str(form.get("path") or "")
        if loginPath and loginPath in str(getattr(response, "url", "") or ""):
            return True
        return False

    async def _send(self, section: Dict[str, Any], variables: Dict[str, Any]):
        method = str(section.get("method") or "GET").upper()
        url = self.absoluteUrl(fillTemplate(section["path"], variables, encode=True))
        params = {}
        for key, value in (section.get("params") or {}).items():
            filled = fillTemplate(str(value), variables, encode=False)
            if filled != "":
                params[key] = filled
        isForm = self.login.get("method") == "form"
        if isForm and not self._loggedIn:
            await self._formLogin()
        kwargs = {"params": params} if method == "GET" else {"data": params}
        allow = (401, 403) if isForm else ()
        response = await self.request(method, url, allowStatus=allow, **kwargs)
        if isForm and self._sessionExpired(response):
            await self._formLogin()
            response = await self.request(method, url, **kwargs)
        return response

    async def checkCapabilities(self) -> str:
        method = self.login.get("method", "none")
        if method == "form":
            await self._formLogin()
        check = self.login.get("check")
        if check:
            response = await self.request("GET", self.absoluteUrl(check["path"]))
            if check["contains"] not in (response.text or ""):
                raise IndexerError(
                    f"Signed-in check failed. The page at {check['path']} does not contain '{check['contains']}'",
                    stage="auth",
                )
            return f"Signed in with {method} login. Check page confirmed"
        return f"Login method {method}" + (". Signed in" if method == "form" else "")

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    def parseAnswer(
        self, section: Dict[str, Any], body: str, scope: str, variables: Dict[str, Any]
    ) -> List[TorrentRelease]:
        releases = []
        fields = section["fields"]
        for position, row in enumerate(readRows(section, body), start=1):
            values: Dict[str, Optional[str]] = {}
            for name, spec in fields.items():
                try:
                    values[name] = readField(name, spec, row, variables)
                except Exception as e:
                    raise IndexerError(
                        f"Row {position}: field {name} could not be read ({e})", stage="parse", field=name
                    )
            title = values.get("title")
            if not title:
                raise IndexerError(f"Row {position}: field title is empty", stage="parse", field="title")
            if not any(values.get(name) for name in ("download", "magnet", "infohash")):
                raise IndexerError(
                    f"Row {position} ('{title}'): download, magnet and infohash are all empty",
                    stage="parse",
                    field="download",
                )
            size = None
            if values.get("size"):
                text = values["size"]
                size = toInt(text) if re.fullmatch(r"[\d,.]+", text) else self.parse_size(text)
                if size is None:
                    raise IndexerError(
                        f"Row {position}: field size '{text}' is neither a byte count nor a size such as 1.4 GB",
                        stage="parse",
                        field="size",
                    )
            counts = {}
            for name in ("seeders", "leechers"):
                text = values.get(name)
                counts[name] = toInt(text) if text else None
                if text and counts[name] is None:
                    raise IndexerError(
                        f"Row {position}: field {name} '{text}' is not a number", stage="parse", field=name
                    )
            publishDate = None
            if values.get("publishDate"):
                text = values["publishDate"]
                pattern = (fields.get("publishDate") or {}).get("dateFormat")
                if pattern:
                    from datetime import datetime

                    try:
                        publishDate = datetime.strptime(text, pattern)
                    except ValueError:
                        publishDate = None
                else:
                    publishDate = parseDate(text)
                if publishDate is None:
                    raise IndexerError(
                        f"Row {position}: field publishDate '{text}' is not a date"
                        + (f" in the format {pattern}" if pattern else ""),
                        stage="parse",
                        field="publishDate",
                    )
            magnet = values.get("magnet")
            if magnet and not magnet.startswith("magnet:"):
                raise IndexerError(
                    f"Row {position}: field magnet does not start with magnet:", stage="parse", field="magnet"
                )
            infoHash = values.get("infohash")
            if infoHash and not re.fullmatch(r"[0-9a-fA-F]{40}", infoHash):
                raise IndexerError(
                    f"Row {position}: field infohash '{infoHash}' is not a 40 character hex hash",
                    stage="parse",
                    field="infohash",
                )
            releases.append(
                self.makeRelease(
                    title=title,
                    scope=scope,
                    downloadUrl=values.get("download"),
                    magnet=magnet,
                    infoHash=infoHash,
                    size=size,
                    seeders=counts["seeders"],
                    leechers=counts["leechers"],
                    publishDate=publishDate,
                    uploader=values.get("uploader"),
                    detailUrl=values.get("details"),
                )
            )
        return releases

    async def searchScope(self, query, scope, context, limit) -> List[TorrentRelease]:
        section = self.definition["search"]
        variables = self._variables(query, scope, context)
        response = await self._send(section, variables)
        return self.parseAnswer(section, response.text or "", scope, variables)

    async def fetchRecent(self) -> List[TorrentRelease]:
        section = self.definition.get("rss") or self.definition["search"]
        releases = []
        for scope in self.config.mediaTypes or ["movies"]:
            variables = self._variables("", scope, None)
            response = await self._send(section, variables)
            releases.extend(self.parseAnswer(section, response.text or "", scope, variables))
        return releases

    async def downloadTorrentFile(self, link: str) -> bytes:
        if self.login.get("method") == "form" and not self._loggedIn:
            await self._formLogin()
        response = await self.request("GET", self.absoluteUrl(link) or link)
        return response.content
