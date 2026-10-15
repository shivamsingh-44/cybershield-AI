import os
from googleapiclient.discovery import build


def search_youtube(query, max_results=10):
    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        return {
            "error": "YouTube API key not found. Set YOUTUBE_API_KEY first.",
            "videos": [],
        }

    try:
        youtube = build(
            "youtube",
            "v3",
            developerKey=api_key,
        )

        response = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results,
            order="date",
        ).execute()

        videos = []

        for item in response.get("items", []):
            snippet = item["snippet"]
            video_id = item["id"]["videoId"]

            videos.append({
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "description": snippet.get("description", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            })

        return {"videos": videos}

    except Exception as error:
        return {
            "error": str(error),
            "videos": [],
        }