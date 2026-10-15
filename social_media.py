"""YouTube Data API helper for CyberShield AI.

Place this file beside app.py and .env. The API key is loaded from the project's
.env file explicitly, so the current working directory does not matter.
"""

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
ENV_PATH = APP_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/search"
REQUEST_TIMEOUT_SECONDS = 20


def _get_api_key() -> str:
    """Return the key from environment or the project .env file."""
    # Reload so a newly edited .env can be picked up after restarting/importing.
    load_dotenv(dotenv_path=ENV_PATH, override=False)
    return (os.getenv("YOUTUBE_API_KEY") or "").strip().strip('"').strip("'")


def search_youtube(query: str, max_results: int = 10) -> dict[str, Any]:
    """Search public YouTube video metadata and return a predictable result shape."""
    query = (query or "").strip()
    if not query:
        return {"videos": [], "error": "Enter a YouTube search keyword."}

    api_key = _get_api_key()
    if not api_key:
        return {
            "videos": [],
            "error": (
                "YouTube API key not found. Add "
                "YOUTUBE_API_KEY=your_actual_key to the project .env file at "
                f"{ENV_PATH}, then fully restart Streamlit."
            ),
        }

    try:
        limit = max(1, min(int(max_results), 25))
    except (TypeError, ValueError):
        limit = 10

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": limit,
        "key": api_key,
        "safeSearch": "moderate",
    }

    try:
        response = requests.get(
            YOUTUBE_API_URL,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            try:
                payload = response.json()
                api_error = payload.get("error", {}).get("message", response.text)
                reason = ""
                errors = payload.get("error", {}).get("errors", [])
                if errors:
                    reason = errors[0].get("reason", "")
            except ValueError:
                api_error, reason = response.text, ""

            if response.status_code == 403:
                return {
                    "videos": [],
                    "error": (
                        "YouTube API returned 403. Check that YouTube Data API v3 "
                        "is enabled, the key is valid, its API restrictions allow "
                        "YouTube Data API v3, and quota is available. "
                        f"Details: {api_error} {('Reason: ' + reason) if reason else ''}"
                    ),
                }
            if response.status_code == 400:
                return {
                    "videos": [],
                    "error": f"YouTube API rejected the request: {api_error}",
                }
            return {
                "videos": [],
                "error": f"YouTube API error ({response.status_code}): {api_error}",
            }

        payload = response.json()
        videos = []
        for item in payload.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue

            videos.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title", "Untitled video"),
                    "channel": snippet.get("channelTitle", "Unknown channel"),
                    "published_at": snippet.get("publishedAt", "Unknown"),
                    "description": snippet.get("description", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                }
            )

        return {"videos": videos, "error": None}

    except requests.Timeout:
        return {
            "videos": [],
            "error": "The YouTube API request timed out. Please try again.",
        }
    except requests.RequestException as exc:
        return {
            "videos": [],
            "error": f"Could not connect to YouTube API: {exc}",
        }
    except (ValueError, TypeError) as exc:
        return {
            "videos": [],
            "error": f"Could not read YouTube API response: {exc}",
        }


def youtube_key_status() -> dict[str, str | bool]:
    """Safe diagnostic: reports whether the key exists, never prints the key."""
    key = _get_api_key()
    return {
        "env_file": str(ENV_PATH),
        "env_file_exists": ENV_PATH.is_file(),
        "key_loaded": bool(key),
    }
