"""
Audio language detection for release names.

Language words are matched only in the tag area of a release name, which starts
after the media title ends. The title ends at the release year, a season or
episode marker, or the first quality marker, whichever comes first. This keeps
titles such as The Italian Job or The French Dispatch from being read as Italian
or French releases.
"""

import re
from typing import List, Optional

MULTI_LANGUAGE = "multi"

# Language assumed when a release name carries no language tag. Scene and P2P
# naming leaves English and original-language releases untagged.
UNTAGGED_LANGUAGE = "en"

# Release name tokens that name an audio language, mapped to ISO 639-1 codes.
LANGUAGE_TOKENS = {
    "ENGLISH": "en",
    "ENG": "en",
    "SPANISH": "es",
    "SPA": "es",
    "ESP": "es",
    "CASTELLANO": "es",
    "LATINO": "es",
    "FRENCH": "fr",
    "TRUEFRENCH": "fr",
    "FRE": "fr",
    "FRA": "fr",
    "VFF": "fr",
    "VFQ": "fr",
    "VF": "fr",
    "VF2": "fr",
    "GERMAN": "de",
    "GER": "de",
    "DEU": "de",
    "ITALIAN": "it",
    "ITA": "it",
    "JAPANESE": "ja",
    "JPN": "ja",
    "JAP": "ja",
    "KOREAN": "ko",
    "KOR": "ko",
    "CHINESE": "zh",
    "CHI": "zh",
    "CHS": "zh",
    "CHT": "zh",
    "MANDARIN": "zh",
    "CANTONESE": "zh",
    "PORTUGUESE": "pt",
    "POR": "pt",
    "RUSSIAN": "ru",
    "RUS": "ru",
    "HINDI": "hi",
    "HIN": "hi",
    "ARABIC": "ar",
    "ARA": "ar",
    "DUTCH": "nl",
    "DUT": "nl",
    "NLD": "nl",
    "FLEMISH": "nl",
    "POLISH": "pl",
    "POL": "pl",
    "TURKISH": "tr",
    "TUR": "tr",
    "SWEDISH": "sv",
    "NORWEGIAN": "no",
    "DANISH": "da",
    "FINNISH": "fi",
    "CZECH": "cs",
    "HUNGARIAN": "hu",
    "GREEK": "el",
    "HEBREW": "he",
    "UKRAINIAN": "uk",
    "THAI": "th",
    "VIETNAMESE": "vi",
    "INDONESIAN": "id",
    "TAMIL": "ta",
    "TELUGU": "te",
}

# Tokens that mark a release as carrying more than one audio language.
MULTI_TOKENS = {"MULTI", "DUAL"}

# Token that marks a dual language release when it directly follows a language token.
DUAL_LANGUAGE_TOKEN = "DL"

# Tokens that turn the language before them into a subtitle language, as in ENG SUBS.
SUBTITLE_TOKENS = {"SUB", "SUBS", "SUBBED", "SUBTITLE", "SUBTITLES", "SUBTITLED"}

# Tokens that only appear in the quality part of a release name.
QUALITY_TOKENS = {
    "4K",
    "8K",
    "UHD",
    "BLURAY",
    "BLU",
    "BDRIP",
    "BRRIP",
    "BDREMUX",
    "REMUX",
    "WEB",
    "WEBDL",
    "WEBRIP",
    "HDRIP",
    "HDTV",
    "SDTV",
    "PDTV",
    "DVDRIP",
    "DVD",
    "DVDSCR",
    "HDCAM",
    "CAM",
    "TELESYNC",
    "X264",
    "X265",
    "H264",
    "H265",
    "HEVC",
    "AV1",
    "XVID",
}

# ISO 639-1 codes accepted inside brackets anywhere in the name, as in [FR].
BRACKET_CODES = set(LANGUAGE_TOKENS.values())

_tokenSplit = re.compile(r"[^A-Z0-9]+")
_resolutionToken = re.compile(r"^\d{3,4}[PI]$")
_yearToken = re.compile(r"^(19|20)\d{2}$")
_episodeToken = re.compile(r"^(S\d{1,2}(E\d{1,4})*|\d{1,2}X\d{2,3})$")
_bracketCode = re.compile(r"\[([A-Z]{2})\]")


def _isQualityToken(token: str) -> bool:
    return token in QUALITY_TOKENS or bool(_resolutionToken.match(token))


def tagAreaTokens(title: str) -> List[str]:
    """
    Return the tokens of a release name that come after the media title.

    Returns an empty list when the name has no year, episode, or quality marker,
    since the title end cannot be located.
    """
    tokens = [t for t in _tokenSplit.split((title or "").upper()) if t]

    qualityIndex = next((i for i, t in enumerate(tokens) if _isQualityToken(t)), None)
    episodeIndex = next((i for i, t in enumerate(tokens) if _episodeToken.match(t)), None)

    # The release year is the last year before the quality part, so a title that
    # contains a year (Blade Runner 2049 2017) still ends at the release year.
    yearLimit = qualityIndex if qualityIndex is not None else len(tokens)
    yearIndex = None
    for i in range(yearLimit):
        if _yearToken.match(tokens[i]):
            yearIndex = i

    # Markers that end the title are themselves skipped. The first quality token
    # can never be a language, so starting after it loses nothing.
    markers = [i for i in (yearIndex, episodeIndex, qualityIndex) if i is not None]
    if not markers:
        return []
    return tokens[min(markers) + 1 :]


def detectLanguages(title: str) -> List[str]:
    """
    Return every audio language named in the tag area of a release name, in the
    order they appear. MULTI or DUAL adds the multi marker. Languages followed by
    a subtitle token are left out.
    """
    tokens = tagAreaTokens(title)
    found: List[str] = []
    for i, token in enumerate(tokens):
        # DL after a language, as in GERMAN.DL, marks a dual language release. DL on its
        # own is part of WEB-DL and is ignored.
        previousToken = tokens[i - 1] if i > 0 else None
        isDualLanguage = token == DUAL_LANGUAGE_TOKEN and previousToken in LANGUAGE_TOKENS
        if token in MULTI_TOKENS or isDualLanguage:
            if MULTI_LANGUAGE not in found:
                found.append(MULTI_LANGUAGE)
            continue
        code = LANGUAGE_TOKENS.get(token)
        if code is None:
            continue
        nextToken = tokens[i + 1] if i + 1 < len(tokens) else None
        if nextToken in SUBTITLE_TOKENS:
            continue
        if code not in found:
            found.append(code)
    return found


def detectLanguage(title: str) -> str:
    """
    Return one language code for a release name.

    Returns the multi marker when the name has MULTI or DUAL or names more than one
    language, the single language code when it names one, a bracketed code such as
    [FR] when the tag area names none, and the untagged default otherwise.
    """
    found = detectLanguages(title)
    if MULTI_LANGUAGE in found or len(found) > 1:
        return MULTI_LANGUAGE
    if found:
        return found[0]

    bracketMatch = _bracketCode.search((title or "").upper())
    if bracketMatch:
        code = bracketMatch.group(1).lower()
        if code in BRACKET_CODES:
            return code

    return UNTAGGED_LANGUAGE


def languageAllowed(language: Optional[str], allowedLanguages: Optional[List[str]]) -> bool:
    """
    Check a detected release language against a profile's language list.

    An empty list allows every language. A multi release passes when the list
    holds more than one language or names multi itself.
    """
    if not allowedLanguages or not language:
        return True
    if language == MULTI_LANGUAGE:
        return len(allowedLanguages) > 1 or MULTI_LANGUAGE in allowedLanguages
    return language in allowedLanguages
