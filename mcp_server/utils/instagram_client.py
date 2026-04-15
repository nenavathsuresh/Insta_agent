import requests
from typing import Dict, Any,Optional
from mcp_server.config.settings import settings
from mcp_server.utils.logger import logger


class InstagramClient:
    """
    Client wrapper for interacting with Instagram Graph API.

    Provides methods to:
    - Fetch profile details
    - Retrieve posts and media
    - Manage comments (get, reply, hide, delete)
    - Fetch insights (account + media)
    - Publish content (photo, video, reel, carousel, story)
    - Hashtag search
    - Tagged media
    - Mentions
    - Business discovery
    - Direct messaging (conversations + messages)
    - Stories
    - Live media

    Designed for use in MCP tools and agent-based workflows.
    """

    BASE_URL = "https://graph.facebook.com/v25.0"

    def __init__(self):
        """
        Initialize Instagram client with access token and user ID from settings.
        """
        self.access_token = settings.INSTAGRAM_ACCESS_TOKEN
        self.user_id = settings.INSTAGRAM_USER_ID
        self.page_id = settings.INSTAGRAM_PAGE_ID
        token = self.access_token or ""
        token_suffix = token[-8:] if token else ""
        logger.info(
            "access_token present={} length={} suffix={}",
            bool(token),
            len(token),
            token_suffix,
        )

    def _messaging_config_error(self) -> Dict[str, Any]:
        return {
            "error": {
                "message": (
                    "Instagram messaging requires INSTAGRAM_PAGE_ID and a Page Access Token "
                    "with Messenger API for Instagram permissions."
                )
            }
        }

    def _sanitize_url(self, url: str) -> str:
        if "access_token=" not in url:
            return url
        prefix, _, _ = url.partition("access_token=")
        return f"{prefix}access_token=REDACTED"

    def _make_request(self, method: str, endpoint: str, params=None, data=None) -> Dict[str, Any]:
        """
        Internal helper to make HTTP requests to Instagram Graph API.

        Args:
            method (str): HTTP method ("GET", "POST", or "DELETE")
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
            elif method == "DELETE":
                response = requests.delete(url, params=params)
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

    # ---------------------------------------------------------------
    # 📊 PROFILE
    # ---------------------------------------------------------------

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
                "fields": "id,username,followers_count,media_count,account_type,biography,website,profile_picture_url,name"
            },
        )

    # ---------------------------------------------------------------
    # 📸 MEDIA (POSTS)
    # ---------------------------------------------------------------

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
                "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count"
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
                "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count,children"
            },
        )

    # ---------------------------------------------------------------
    # 💬 COMMENTS
    # ---------------------------------------------------------------

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
                "fields": "id,text,username,timestamp,replies,like_count,hidden"
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

    def hide_comment(self, comment_id: str, hide: bool = True) -> Dict[str, Any]:
        """
        Hide or unhide a comment on a media post.

        Args:
            comment_id (str): Comment ID
            hide (bool): True to hide, False to unhide

        Returns:
            dict: API response confirming hide/unhide action
        """
        return self._make_request(
            "POST",
            comment_id,
            data={
                "hide": str(hide).lower()
            },
        )

    def delete_comment(self, comment_id: str) -> Dict[str, Any]:
        """
        Delete a comment from a media post.

        Args:
            comment_id (str): Comment ID to delete

        Returns:
            dict: API response confirming deletion ({"success": true})
        """
        return self._make_request(
            "DELETE",
            comment_id,
        )

    def post_comment(self, media_id: str, message: str) -> Dict[str, Any]:
        """
        Post a new top-level comment on a media post.

        Args:
            media_id (str): Instagram media ID
            message (str): Comment text

        Returns:
            dict: API response with the new comment ID
        """
        return self._make_request(
            "POST",
            f"{media_id}/comments",
            data={
                "message": message
            },
        )

    # ---------------------------------------------------------------
    # 📈 INSIGHTS
    # ---------------------------------------------------------------

    def get_account_insights(self, period: str = "day") -> Dict[str, Any]:
        """
        Fetch account-level insights such as impressions, reach, and profile views.

        Args:
            period (str): Aggregation period — "day", "week", or "days_28"

        Returns:
            dict: Insights metrics for the Instagram account.
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/insights",
            params={
                "metric": "impressions,reach,profile_views,accounts_engaged,total_interactions,follower_count",
                "period": period
            },
        )

    def get_media_insights(self, media_id: str) -> Dict[str, Any]:
        """
        Fetch performance insights for a specific media post.

        Args:
            media_id (str): Instagram media ID

        Returns:
            dict: Metrics such as engagement, impressions, reach, saved, and video views.
        """
        return self._make_request(
            "GET",
            f"{media_id}/insights",
            params={
                "metric": "engagement,impressions,reach,saved,video_views,likes,comments,shares"
            },
        )

    def get_follower_demographics(self) -> Dict[str, Any]:
        """
        Fetch audience demographic breakdown — age, gender, city, country.

        Returns:
            dict: Audience demographic data.
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/insights",
            params={
                "metric": "audience_city,audience_country,audience_gender_age,audience_locale",
                "period": "lifetime"
            },
        )

    def get_online_followers(self) -> Dict[str, Any]:
        """
        Fetch hourly breakdown of when followers are online.

        Returns:
            dict: Online follower counts per hour of the day.
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/insights",
            params={
                "metric": "online_followers",
                "period": "lifetime"
            },
        )

    # ---------------------------------------------------------------
    # ✍️ PUBLISHING — PHOTO
    # ---------------------------------------------------------------

    def create_media_container(self, image_url: str, caption: str) -> Dict[str, Any]:
        """
        Create a media container for publishing a new Instagram photo post.

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
        High-level method to create and publish an Instagram photo post.

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

    # ---------------------------------------------------------------
    # 🎬 PUBLISHING — VIDEO / REEL
    # ---------------------------------------------------------------

    def create_video_container(
        self,
        video_url: str,
        caption: str,
        media_type: str = "REELS",
        thumb_offset: Optional[int] = None,
        share_to_feed: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a container for a video or Reel post.

        Args:
            video_url (str): Publicly accessible video URL
            caption (str): Caption text
            media_type (str): "REELS" (default) or "VIDEO"
            thumb_offset (int, optional): Millisecond offset for thumbnail frame
            share_to_feed (bool): Whether to also share Reel to main feed

        Returns:
            dict: Container ID for publishing
        """
        payload: Dict[str, Any] = {
            "media_type": media_type,
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": str(share_to_feed).lower(),
        }
        if thumb_offset is not None:
            payload["thumb_offset"] = thumb_offset

        return self._make_request(
            "POST",
            f"{self.user_id}/media",
            data=payload,
        )

    def check_container_status(self, container_id: str) -> Dict[str, Any]:
        """
        Poll the upload status of a video/reel media container.

        Args:
            container_id (str): Media container ID returned during creation

        Returns:
            dict: status_code field — "EXPIRED", "ERROR", "FINISHED", "IN_PROGRESS", or "PUBLISHED"
        """
        return self._make_request(
            "GET",
            container_id,
            params={"fields": "status_code,status"},
        )

    def publish_reel(self, video_url: str, caption: str) -> Dict[str, Any]:
        """
        High-level method: create a Reel container and publish it.
        Note: video processing may take time; use check_container_status to poll.

        Args:
            video_url (str): Publicly accessible video URL
            caption (str): Caption text

        Returns:
            dict: Published post response or container status on pending
        """
        container = self.create_video_container(video_url, caption, media_type="REELS")

        if "id" not in container:
            logger.error("Failed to create reel container")
            return container

        return self.publish_media(container["id"])

    # ---------------------------------------------------------------
    # 🖼️ PUBLISHING — CAROUSEL
    # ---------------------------------------------------------------

    def create_carousel_item(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an individual carousel item container (image or video).

        Args:
            image_url (str, optional): Public image URL
            video_url (str, optional): Public video URL

        Returns:
            dict: Item container ID to collect for carousel creation
        """
        payload: Dict[str, Any] = {"is_carousel_item": "true"}
        if image_url:
            payload["image_url"] = image_url
        elif video_url:
            payload["media_type"] = "VIDEO"
            payload["video_url"] = video_url
        else:
            return {"error": {"message": "Must provide image_url or video_url"}}

        return self._make_request(
            "POST",
            f"{self.user_id}/media",
            data=payload,
        )

    def create_carousel_container(
        self, children_ids: list, caption: str
    ) -> Dict[str, Any]:
        """
        Create a carousel post container from a list of item container IDs.

        Args:
            children_ids (list): List of item container IDs (2–10 items)
            caption (str): Caption for the carousel post

        Returns:
            dict: Carousel container ID for publishing
        """
        return self._make_request(
            "POST",
            f"{self.user_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": caption,
            },
        )

    def publish_carousel(self, image_urls: list, caption: str) -> Dict[str, Any]:
        """
        High-level method: upload each image as a carousel item then publish.

        Args:
            image_urls (list): List of 2–10 public image URLs
            caption (str): Caption for the carousel

        Returns:
            dict: Published post response
        """
        if not 2 <= len(image_urls) <= 10:
            return {"error": {"message": "Carousel requires between 2 and 10 images"}}

        item_ids = []
        for url in image_urls:
            item = self.create_carousel_item(image_url=url)
            if "id" not in item:
                logger.error(f"Failed to create carousel item for URL: {url}")
                return item
            item_ids.append(item["id"])

        carousel = self.create_carousel_container(item_ids, caption)
        if "id" not in carousel:
            logger.error("Failed to create carousel container")
            return carousel

        return self.publish_media(carousel["id"])

    # ---------------------------------------------------------------
    # 📖 STORIES
    # ---------------------------------------------------------------

    def create_story_container(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a media container for an Instagram Story.

        Args:
            image_url (str, optional): Public URL of the story image
            video_url (str, optional): Public URL of the story video

        Returns:
            dict: Container ID for publishing the story
        """
        payload: Dict[str, Any] = {"media_type": "STORIES"}
        if image_url:
            payload["image_url"] = image_url
        elif video_url:
            payload["video_url"] = video_url
        else:
            return {"error": {"message": "Must provide image_url or video_url for story"}}

        return self._make_request(
            "POST",
            f"{self.user_id}/media",
            data=payload,
        )

    def publish_story(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        High-level method to create and publish an Instagram Story.

        Args:
            image_url (str, optional): Public image URL
            video_url (str, optional): Public video URL

        Returns:
            dict: Published story response
        """
        container = self.create_story_container(image_url=image_url, video_url=video_url)

        if "id" not in container:
            logger.error("Failed to create story container")
            return container

        return self.publish_media(container["id"])

    def get_stories(self) -> Dict[str, Any]:
        """
        Retrieve current active stories for the account.

        Returns:
            dict: List of story media objects with id, media_type, media_url, timestamp.
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/stories",
            params={
                "fields": "id,media_type,media_url,timestamp,permalink"
            },
        )

    # ---------------------------------------------------------------
    # #️⃣  HASHTAG SEARCH
    # ---------------------------------------------------------------

    def search_hashtag(self, hashtag: str) -> Dict[str, Any]:
        """
        Look up the ID for an Instagram hashtag.

        Args:
            hashtag (str): Hashtag name without the # symbol (e.g. "travel")

        Returns:
            dict: Hashtag ID used for fetching top/recent media
        """
        return self._make_request(
            "GET",
            "ig_hashtag_search",
            params={
                "user_id": self.user_id,
                "q": hashtag,
            },
        )

    def get_hashtag_top_media(self, hashtag_id: str) -> Dict[str, Any]:
        """
        Fetch top media for a given hashtag ID.

        Args:
            hashtag_id (str): Hashtag ID from search_hashtag()

        Returns:
            dict: Top media posts tagged with the hashtag
        """
        return self._make_request(
            "GET",
            f"{hashtag_id}/top_media",
            params={
                "user_id": self.user_id,
                "fields": "id,caption,media_type,media_url,permalink,timestamp",
            },
        )

    def get_hashtag_recent_media(self, hashtag_id: str) -> Dict[str, Any]:
        """
        Fetch recently published media for a given hashtag ID.

        Args:
            hashtag_id (str): Hashtag ID from search_hashtag()

        Returns:
            dict: Recent media posts tagged with the hashtag
        """
        return self._make_request(
            "GET",
            f"{hashtag_id}/recent_media",
            params={
                "user_id": self.user_id,
                "fields": "id,caption,media_type,media_url,permalink,timestamp",
            },
        )

    def search_hashtag_media(self, hashtag: str, top: bool = True) -> Dict[str, Any]:
        """
        High-level helper: search hashtag then return top or recent media.

        Args:
            hashtag (str): Hashtag name without # (e.g. "travel")
            top (bool): True for top media, False for recent media

        Returns:
            dict: Media posts for the hashtag
        """
        result = self.search_hashtag(hashtag)
        data = result.get("data", [])
        if not data:
            return result

        hashtag_id = data[0]["id"]
        if top:
            return self.get_hashtag_top_media(hashtag_id)
        return self.get_hashtag_recent_media(hashtag_id)

    def get_recently_searched_hashtags(self) -> Dict[str, Any]:
        """
        Return the hashtags this account has searched in the last 7 days.
        Limited to 30 unique hashtags per week by the Graph API.

        Returns:
            dict: List of recently searched hashtag objects
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/recently_searched_hashtags",
        )

    # ---------------------------------------------------------------
    # 🏷️  MENTIONS & TAGGED MEDIA
    # ---------------------------------------------------------------

    def get_tagged_media(self) -> Dict[str, Any]:
        """
        Retrieve media posts in which this account has been tagged by other users.

        Returns:
            dict: List of media where the account is tagged
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/tags",
            params={
                "fields": "id,caption,media_type,media_url,permalink,timestamp,owner"
            },
        )

    def get_mentions(self) -> Dict[str, Any]:
        """
        Retrieve media objects and comments where this account has been @mentioned.

        Returns:
            dict: Mention objects with media/comment context
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/mentions",
            params={
                "fields": "id,caption,media_type,media_url,timestamp,permalink"
            },
        )

    def get_mention_media(self, media_id: str, mentioned_media_id: str) -> Dict[str, Any]:
        """
        Get the fields of a media object where this account was @mentioned in a caption.

        Args:
            media_id (str): Media ID of the post containing the mention
            mentioned_media_id (str): The mentioned_media_id from a mention webhook

        Returns:
            dict: Media details for the mentioned post
        """
        return self._make_request(
            "GET",
            self.user_id,
            params={
                "fields": f"mentioned_media.fields(id,media_url,caption,timestamp).media_id({mentioned_media_id})",
            },
        )

    # ---------------------------------------------------------------
    # 🔍 BUSINESS DISCOVERY
    # ---------------------------------------------------------------

    def discover_business_account(self, username: str) -> Dict[str, Any]:
        """
        Look up the public profile of another Instagram Business or Creator account
        by username (Business Discovery API).

        Args:
            username (str): Target Instagram username (no @ symbol)

        Returns:
            dict: Public profile fields: id, name, username, biography,
                  followers_count, media_count, profile_picture_url, website
        """
        return self._make_request(
            "GET",
            self.user_id,
            params={
                "fields": f"business_discovery.fields(id,name,username,biography,followers_count,media_count,profile_picture_url,website).user_id({username})"
            },
        )

    def discover_business_media(self, username: str) -> Dict[str, Any]:
        """
        Retrieve the recent media of another public Business/Creator account.

        Args:
            username (str): Target Instagram username

        Returns:
            dict: Media list from the target account
        """
        return self._make_request(
            "GET",
            self.user_id,
            params={
                "fields": f"business_discovery.fields(media{{id,caption,media_type,media_url,timestamp,permalink}}).user_id({username})"
            },
        )

    # ---------------------------------------------------------------
    # 💌 MESSAGING (DIRECT MESSAGES)
    # ---------------------------------------------------------------

    def get_conversations(self) -> Dict[str, Any]:
        """
        Fetch all DM conversations for the Instagram account.

        Returns:
            dict: List of conversation objects with id, updated_time, participants
        """
        if not self.page_id:
            return self._messaging_config_error()

        return self._make_request(
            "GET",
            f"{self.page_id}/conversations",
            params={
                "platform": "instagram",
                "fields": "id,updated_time,participants",
            },
        )

    def get_conversation_messages(self, conversation_id: str) -> Dict[str, Any]:
        """
        Retrieve messages from a specific DM conversation.

        Args:
            conversation_id (str): Conversation ID from get_conversations()

        Returns:
            dict: List of messages with id, from, message, timestamp
        """
        return self._make_request(
            "GET",
            f"{conversation_id}/messages",
            params={
                "fields": "id,from,message,attachments,timestamp"
            },
        )

    def send_message(self, recipient_id: str, message_text: str) -> Dict[str, Any]:
        """
        Send a direct message to an Instagram user.

        Args:
            recipient_id (str): IGSID (Instagram-scoped user ID) of the recipient
            message_text (str): Text to send

        Returns:
            dict: API response with message_id and recipient_id
        """
        return self._make_request(
            "POST",
            "me/messages",
            data={
                "recipient": f'{{"id":"{recipient_id}"}}',
                "message": f'{{"text":"{message_text}"}}',
            },
        )

    def send_image_message(self, recipient_id: str, image_url: str) -> Dict[str, Any]:
        """
        Send an image attachment via DM to an Instagram user.

        Args:
            recipient_id (str): IGSID of the recipient
            image_url (str): Publicly accessible image URL

        Returns:
            dict: API response with message_id and recipient_id
        """
        return self._make_request(
            "POST",
            "me/messages",
            data={
                "recipient": f'{{"id":"{recipient_id}"}}',
                "message": f'{{"attachment":{{"type":"image","payload":{{"url":"{image_url}","is_reusable":true}}}}}}',
            },
        )

    # ---------------------------------------------------------------
    # 📡 LIVE VIDEO
    # ---------------------------------------------------------------

    def create_live_media(self, title: str = "") -> Dict[str, Any]:
        """
        Create a live video broadcast object.

        Args:
            title (str): Optional title for the live broadcast

        Returns:
            dict: Live media object with stream_url and id
        """
        payload: Dict[str, Any] = {"media_type": "LIVE"}
        if title:
            payload["title"] = title

        return self._make_request(
            "POST",
            f"{self.user_id}/live_videos",
            data=payload,
        )

    def get_live_media(self, live_video_id: str) -> Dict[str, Any]:
        """
        Fetch details of an active or completed live video.

        Args:
            live_video_id (str): Live video media ID

        Returns:
            dict: Live media fields — status, stream_url, secure_stream_url, title
        """
        return self._make_request(
            "GET",
            live_video_id,
            params={
                "fields": "id,status,stream_url,secure_stream_url,title,comments,likes"
            },
        )

    def end_live_media(self, live_video_id: str) -> Dict[str, Any]:
        """
        End an active live broadcast.

        Args:
            live_video_id (str): Live video media ID

        Returns:
            dict: API response confirming broadcast ended
        """
        return self._make_request(
            "POST",
            live_video_id,
            data={"end_live_video": "true"},
        )

    # ---------------------------------------------------------------
    # 📌 SAVED / BOOKMARKED POSTS (own account)
    # ---------------------------------------------------------------

    def get_saved_media(self) -> Dict[str, Any]:
        """
        Retrieve media saved/bookmarked by this account.

        Returns:
            dict: List of saved media objects
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/saved",
            params={
                "fields": "id,caption,media_type,media_url,permalink,timestamp"
            },
        )

    # ---------------------------------------------------------------
    # 🛍️  PRODUCT TAGGING (Shopping)
    # ---------------------------------------------------------------

    def get_product_catalog(self) -> Dict[str, Any]:
        """
        Retrieve the product catalog linked to this Instagram account.

        Returns:
            dict: Catalog ID and associated product sets
        """
        return self._make_request(
            "GET",
            f"{self.user_id}/catalogs",
            params={"fields": "id,name,product_count"},
        )

    def create_product_tagged_container(
        self, image_url: str, caption: str, product_tags: list
    ) -> Dict[str, Any]:
        """
        Create a media container with product tags for Instagram Shopping.

        Args:
            image_url (str): Public image URL
            caption (str): Caption text
            product_tags (list): List of dicts with keys:
                                 product_id (str), merchant_id (str),
                                 x (float 0.0–1.0), y (float 0.0–1.0)

        Returns:
            dict: Container ID for publishing
        """
        import json
        return self._make_request(
            "POST",
            f"{self.user_id}/media",
            data={
                "image_url": image_url,
                "caption": caption,
                "product_tags": json.dumps(product_tags),
            },
        )
