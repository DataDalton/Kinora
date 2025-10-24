import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.cache import cache_get, cache_set


class AnilistService:
    """
    Anilist GraphQL API service for fetching anime metadata
    """

    API_URL = "https://graphql.anilist.co"

    async def _query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query against Anilist API with caching
        """
        if variables is None:
            variables = {}

        cache_key = f"anilist:{query[:50]}:{str(variables)}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.API_URL,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                raise Exception(f"Anilist API error: {data['errors']}")

            await cache_set(cache_key, data["data"], expire=3600)
            return data["data"]

    async def search_anime(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for anime by title
        """
        gql_query = """
        query ($search: String, $seasonYear: Int) {
          Page(page: 1, perPage: 20) {
            media(search: $search, type: ANIME, seasonYear: $seasonYear, sort: POPULARITY_DESC) {
              id
              idMal
              title {
                romaji
                english
                native
              }
              coverImage {
                large
                extraLarge
              }
              bannerImage
              startDate {
                year
                month
                day
              }
              endDate {
                year
                month
                day
              }
              description
              episodes
              duration
              genres
              averageScore
              popularity
              seasonYear
              season
              format
              source
              studios {
                nodes {
                  name
                }
              }
              isAdult
            }
          }
        }
        """

        variables = {"search": query}
        if year:
            variables["seasonYear"] = year

        data = await self._query(gql_query, variables)
        return data.get("Page", {}).get("media", [])

    async def get_anime(self, anilist_id: int) -> Dict[str, Any]:
        """
        Get detailed anime information
        """
        gql_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            idMal
            title {
              romaji
              english
              native
            }
            coverImage {
              large
              extraLarge
            }
            bannerImage
            startDate {
              year
              month
              day
            }
            endDate {
              year
              month
              day
            }
            description
            episodes
            duration
            genres
            averageScore
            popularity
            seasonYear
            season
            format
            source
            status
            studios {
              nodes {
                name
              }
            }
            isAdult
            characters(perPage: 10, sort: ROLE) {
              nodes {
                id
                name {
                  full
                }
                image {
                  large
                }
              }
            }
            staff(perPage: 5, sort: RELEVANCE) {
              nodes {
                id
                name {
                  full
                }
                primaryOccupations
              }
            }
            relations {
              nodes {
                id
                type
                title {
                  romaji
                  english
                }
                coverImage {
                  large
                }
              }
            }
            externalLinks {
              url
              site
            }
          }
        }
        """

        data = await self._query(gql_query, {"id": anilist_id})
        return data.get("Media", {})

    async def get_trending(self, page: int = 1, per_page: int = 20) -> List[Dict[str, Any]]:
        """
        Get trending anime
        """
        gql_query = """
        query ($page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(type: ANIME, sort: TRENDING_DESC) {
              id
              idMal
              title {
                romaji
                english
              }
              coverImage {
                large
              }
              averageScore
              popularity
              episodes
              seasonYear
              season
            }
          }
        }
        """

        data = await self._query(gql_query, {"page": page, "perPage": per_page})
        return data.get("Page", {}).get("media", [])

    async def get_popular(self, page: int = 1, per_page: int = 20) -> List[Dict[str, Any]]:
        """
        Get popular anime
        """
        gql_query = """
        query ($page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(type: ANIME, sort: POPULARITY_DESC) {
              id
              idMal
              title {
                romaji
                english
              }
              coverImage {
                large
              }
              averageScore
              popularity
              episodes
              seasonYear
              season
            }
          }
        }
        """

        data = await self._query(gql_query, {"page": page, "perPage": per_page})
        return data.get("Page", {}).get("media", [])

    async def get_upcoming(self, page: int = 1, per_page: int = 20) -> List[Dict[str, Any]]:
        """
        Get upcoming anime for next season
        """
        gql_query = """
        query ($page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(type: ANIME, status: NOT_YET_RELEASED, sort: POPULARITY_DESC) {
              id
              idMal
              title {
                romaji
                english
              }
              coverImage {
                large
              }
              averageScore
              popularity
              episodes
              seasonYear
              season
            }
          }
        }
        """

        data = await self._query(gql_query, {"page": page, "perPage": per_page})
        return data.get("Page", {}).get("media", [])

    def parse_anime_data(self, anilist_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Anilist data into our database format
        """
        title_obj = anilist_data.get("title", {})
        title = title_obj.get("english") or title_obj.get("romaji") or title_obj.get("native")
        original_title = title_obj.get("romaji")

        start_date = self._parse_anilist_date(anilist_data.get("startDate"))

        studios = [studio.get("name") for studio in anilist_data.get("studios", {}).get("nodes", [])]

        return {
            "title": title,
            "original_title": original_title,
            "overview": self._clean_description(anilist_data.get("description")),
            "poster_path": anilist_data.get("coverImage", {}).get("extraLarge") or anilist_data.get("coverImage", {}).get("large"),
            "backdrop_path": anilist_data.get("bannerImage"),
            "release_date": start_date,
            "genres": [{"name": genre} for genre in anilist_data.get("genres", [])],
            "rating": anilist_data.get("averageScore") / 10 if anilist_data.get("averageScore") else None,  # Convert to 0-10 scale
            "vote_count": None,  # Anilist doesn't provide this
            "popularity": anilist_data.get("popularity"),
            "anilist_id": anilist_data.get("id"),
            "mal_id": anilist_data.get("idMal"),
            "episodes": anilist_data.get("episodes"),
            "duration": anilist_data.get("duration"),
            "season_year": anilist_data.get("seasonYear"),
            "season_period": anilist_data.get("season"),
            "format": anilist_data.get("format"),
            "source": anilist_data.get("source"),
            "studios": studios,
            "is_adult": anilist_data.get("isAdult", False),
        }

    def _parse_anilist_date(self, date_obj: Optional[Dict[str, int]]) -> Optional[datetime]:
        """
        Parse Anilist date object to datetime
        """
        if not date_obj:
            return None

        year = date_obj.get("year")
        month = date_obj.get("month") or 1
        day = date_obj.get("day") or 1

        if not year:
            return None

        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    def _clean_description(self, description: Optional[str]) -> Optional[str]:
        """
        Clean HTML tags from Anilist description
        """
        if not description:
            return None

        import re
        clean = re.sub("<.*?>", "", description)
        return clean.strip()


anilist_service = AnilistService()
