from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.metadata_refresh.refresh_all_metadata")
def refresh_all_metadata():
    """
    Refresh metadata for all media in library
    Production implementation will:
    - Query TMDB/Anilist for updated metadata
    - Update posters, ratings, release dates
    - Check for new seasons/episodes
    """
    # TODO: Implement metadata refresh
    return {"status": "success", "items_updated": 0}
