import requests
from typing import Dict, Any
from app.config.settings import settings
from app.utils.logger import logger


class InstagramClient:
    """
    Client wrapper for interacting with Instagram Graph API.

    Provides methods to:
    - Fetch profile details
    - Retrieve posts and media
    - Manage comments
    - Fetch insights
    - Publish content

    Designed for use in MCP tools and agent-based workflows.
    """

    BASE_URL = "https://graph.facebook.com/v25.0"

    def __init__(self):
        """
        Initialize Instagram client with access token and user ID from settings.
        """
        self.access_token = settings.INSTAGRAM_ACCESS_TOKEN
        self.user_id = settings.INSTAGRAM_USER_ID
        token = self.access_token or ""
        token_suffix = token[-8:] if token else ""
        logger.info(
            "access_token present={} length={} suffix={}",
            bool(token),
            len(token),
            token_suffix,
        )

    def _sanitize_url(self, url: str) -> str:
        if "access_token=" not in url:
            return url
        prefix, _, _ = url.partition("access_token=")
        return f"{prefix}access_token=REDACTED"

    def _make_request(self, method: str, endpoint: str, params=None, data=None) -> Dict[str, Any]:
        """
        Internal helper to make HTTP requests to Instagram Graph API.

        Args:
            method (str): HTTP method ("GET" or "POST")
            endpoint (str): API endpoint (relative path)
            params (dict, optional): Query parameters
            data (dict, optional): POST body data

        Returns:
            dict: JSON response from API or error message
        """
        url = f"{self.BASE_URL}/{endpoint}"

        if params is None:
            params = {}

        params["access_token"] = self.access_token

        try:
            if method == "GET":
                response = requests.get(url, params=params)
            elif method == "POST":
                payload = data.copy() if data else params.copy()
                payload["access_token"] = self.access_token
                response = requests.post(url, data=payload)
            else:
                raise ValueError("Unsupported HTTP method")

            logger.info(f"{method} {endpoint} -> {response.status_code}")
            response_json = response.json()

            if response.ok:
                return response_json

            sanitized_url = self._sanitize_url(response.url)
            logger.error(
                f"Instagram API error {response.status_code} for {url}: {response_json}"
            )
            return {
                "error": {
                    "status_code": response.status_code,
                    "url": sanitized_url,
                    "details": response_json,
                }
            }

        except requests.exceptions.RequestException as e:
            request_url = ""
            if getattr(e, "request", None) is not None and e.request.url:
                request_url = self._sanitize_url(e.request.url)
            logger.error(f"Instagram API request exception for {request_url}: {str(e)}")
            return {
                "error": {
                    "message": str(e),
                    "url": request_url,
                }
            }

    # -------------------------------
    # 📊 PROFILE
    # -------------------------------

    def get_profile(self) -> Dict[str, Any]:
        """
        Fetch Instagram business account profile details.

        Returns:
            dict: Profile information including username, followers count,
                  media count, account type, and biography.
        """
        return self._make_request(
            "GET",
            self.user_id,
            params={
                "fields": "id,username,followers_count"
            },
        )

    # -------------------------------
    # 📸 MEDIA (POSTS)
    # -------------------------------

    def get_media_list(self) -> Dict[str, Any]:
        """
        Retrieve list of media posts for the Instagram account.

        Returns:
            dict: List of media objects including id, caption, media type,
                  media URL, and timestamp.
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/media",
            params={
                "fields": "id,caption,media_type,media_url,timestamp"
            },
        )

    def get_media_details(self, media_id: str) -> Dict[str, Any]:
        """
        Fetch detailed information about a specific media post.

        Args:
            media_id (str): Instagram media ID

        Returns:
            dict: Media details including caption, type, URL, and timestamp.
        """
        return self._make_request(
            "GET",
            media_id,
            params={
                "fields": "id,caption,media_type,media_url,timestamp"
            },
        )

    # -------------------------------
    # 💬 COMMENTS
    # -------------------------------

    def get_comments(self, media_id: str) -> Dict[str, Any]:
        """
        Retrieve comments for a specific media post.

        Args:
            media_id (str): Instagram media ID

        Returns:
            dict: List of comments with text, username, and timestamp.
        """
        return self._make_request(
            "GET",
            f"{media_id}/comments",
            params={
                "fields": "id,text,username,timestamp"
            },
        )

    def reply_to_comment(self, comment_id: str, message: str) -> Dict[str, Any]:
        """
        Reply to a specific comment on Instagram.

        Args:
            comment_id (str): Comment ID to reply to
            message (str): Reply message

        Returns:
            dict: API response confirming reply creation
        """
        return self._make_request(
            "POST",
            f"{comment_id}/replies",
            data={
                "message": message
            },
        )

    # -------------------------------
    # 📈 INSIGHTS
    # -------------------------------

    def get_account_insights(self) -> Dict[str, Any]:
        """
        Fetch account-level insights such as impressions, reach, and profile views.

        Returns:
            dict: Insights metrics for the Instagram account.
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/insights",
            params={
                "metric": "impressions,reach,profile_views",
                "period": "day"
            },
        )

    def get_media_insights(self, media_id: str) -> Dict[str, Any]:
        """
        Fetch performance insights for a specific media post.

        Args:
            media_id (str): Instagram media ID

        Returns:
            dict: Metrics such as engagement, impressions, and reach.
        """
        return self._make_request(
            "GET",
            f"{media_id}/insights",
            params={
                "metric": "engagement,impressions,reach"
            },
        )

    # -------------------------------
    # ✍️ PUBLISHING
    # -------------------------------

    def create_media_container(self, image_url: str, caption: str) -> Dict[str, Any]:
        """
        Create a media container for publishing a new Instagram post.

        Args:
            image_url (str): Public URL of the image
            caption (str): Caption for the post

        Returns:
            dict: Container ID used for publishing
        """
        return self._make_request(
            "POST",
            f"{self.user_id}/media",
            data={
                "image_url": image_url,
                "caption": caption
            },
        )

    def publish_media(self, creation_id: str) -> Dict[str, Any]:
        """
        Publish a previously created media container.

        Args:
            creation_id (str): Media container ID

        Returns:
            dict: API response confirming post publication
        """
        return self._make_request(
            "POST",
            f"{self.user_id}/media_publish",
            data={
                "creation_id": creation_id
            },
        )

    def publish_post(self, image_url: str, caption: str) -> Dict[str, Any]:
        """
        High-level method to create and publish an Instagram post.

        Args:
            image_url (str): Public image URL
            caption (str): Caption text

        Returns:
            dict: Final response after publishing the post
        """
        container = self.create_media_container(image_url, caption)

        if "id" not in container:
            logger.error("Failed to create media container")
            return container

        return self.publish_media(container["id"])
