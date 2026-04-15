import time
import random
from typing import Any, Dict, List, Optional

from fastmcp.tools import tool
from app.utils.instagram_client import InstagramClient


class InstagramTools:
    """
    MCP tool wrapper around InstagramClient.

    Adds rate-limiting on publish operations and exposes every
    Graph API capability as a plain method (called by @tool functions below).
    """

    def __init__(self):
        self.client = InstagramClient()
        self.last_post_time = 0

    def _check_post_rate_limit(self):
        """Raise if a publish operation was made less than 60 s ago."""
        if time.time() - self.last_post_time < 60:
            raise Exception("Rate limit: wait before posting again")

    def _mark_post_time(self):
        self.last_post_time = time.time()

    # ---------------------------------------------------------------
    # 📊 PROFILE
    # ---------------------------------------------------------------

    def get_profile(self) -> Dict[str, Any]:
        return self.client.get_profile()

    # ---------------------------------------------------------------
    # 📸 MEDIA
    # ---------------------------------------------------------------

    def get_media_list(self) -> Dict[str, Any]:
        return self.client.get_media_list()

    def get_media_details(self, media_id: str) -> Dict[str, Any]:
        return self.client.get_media_details(media_id)

    # ---------------------------------------------------------------
    # 💬 COMMENTS
    # ---------------------------------------------------------------

    def get_comments(self, media_id: str) -> Dict[str, Any]:
        return self.client.get_comments(media_id)

    def reply_to_comment(self, comment_id: str, message: str) -> Dict[str, Any]:
        return self.client.reply_to_comment(comment_id, message)

    def post_comment(self, media_id: str, message: str) -> Dict[str, Any]:
        return self.client.post_comment(media_id, message)

    def hide_comment(self, comment_id: str, hide: bool = True) -> Dict[str, Any]:
        return self.client.hide_comment(comment_id, hide)

    def delete_comment(self, comment_id: str) -> Dict[str, Any]:
        return self.client.delete_comment(comment_id)

    # ---------------------------------------------------------------
    # 📈 INSIGHTS
    # ---------------------------------------------------------------

    def get_account_insights(self, period: str = "day") -> Dict[str, Any]:
        return self.client.get_account_insights(period)

    def get_media_insights(self, media_id: str) -> Dict[str, Any]:
        return self.client.get_media_insights(media_id)

    def get_follower_demographics(self) -> Dict[str, Any]:
        return self.client.get_follower_demographics()

    def get_online_followers(self) -> Dict[str, Any]:
        return self.client.get_online_followers()

    # ---------------------------------------------------------------
    # ✍️ PUBLISHING — PHOTO
    # ---------------------------------------------------------------

    def create_media_container(self, image_url: str, caption: str) -> Dict[str, Any]:
        return self.client.create_media_container(image_url, caption)

    def publish_media(self, creation_id: str) -> Dict[str, Any]:
        self._check_post_rate_limit()
        response = self.client.publish_media(creation_id)
        self._mark_post_time()
        return response

    def publish_post(self, image_url: str, caption: str) -> Dict[str, Any]:
        self._check_post_rate_limit()
        time.sleep(random.randint(5, 15))
        response = self.client.publish_post(image_url, caption)
        self._mark_post_time()
        return response

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
        return self.client.create_video_container(
            video_url, caption, media_type, thumb_offset, share_to_feed
        )

    def check_container_status(self, container_id: str) -> Dict[str, Any]:
        return self.client.check_container_status(container_id)

    def publish_reel(self, video_url: str, caption: str) -> Dict[str, Any]:
        self._check_post_rate_limit()
        time.sleep(random.randint(5, 15))
        response = self.client.publish_reel(video_url, caption)
        self._mark_post_time()
        return response

    # ---------------------------------------------------------------
    # 🖼️ PUBLISHING — CAROUSEL
    # ---------------------------------------------------------------

    def create_carousel_item(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.client.create_carousel_item(image_url, video_url)

    def create_carousel_container(
        self, children_ids: List[str], caption: str
    ) -> Dict[str, Any]:
        return self.client.create_carousel_container(children_ids, caption)

    def publish_carousel(self, image_urls: List[str], caption: str) -> Dict[str, Any]:
        self._check_post_rate_limit()
        time.sleep(random.randint(5, 15))
        response = self.client.publish_carousel(image_urls, caption)
        self._mark_post_time()
        return response

    # ---------------------------------------------------------------
    # 📖 STORIES
    # ---------------------------------------------------------------

    def create_story_container(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.client.create_story_container(image_url, video_url)

    def publish_story(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._check_post_rate_limit()
        response = self.client.publish_story(image_url, video_url)
        self._mark_post_time()
        return response

    def get_stories(self) -> Dict[str, Any]:
        return self.client.get_stories()

    # ---------------------------------------------------------------
    # #️⃣  HASHTAG SEARCH
    # ---------------------------------------------------------------

    def search_hashtag(self, hashtag: str) -> Dict[str, Any]:
        return self.client.search_hashtag(hashtag)

    def get_hashtag_top_media(self, hashtag_id: str) -> Dict[str, Any]:
        return self.client.get_hashtag_top_media(hashtag_id)

    def get_hashtag_recent_media(self, hashtag_id: str) -> Dict[str, Any]:
        return self.client.get_hashtag_recent_media(hashtag_id)

    def search_hashtag_media(self, hashtag: str, top: bool = True) -> Dict[str, Any]:
        return self.client.search_hashtag_media(hashtag, top)

    def get_recently_searched_hashtags(self) -> Dict[str, Any]:
        return self.client.get_recently_searched_hashtags()

    # ---------------------------------------------------------------
    # 🏷️  MENTIONS & TAGGED MEDIA
    # ---------------------------------------------------------------

    def get_tagged_media(self) -> Dict[str, Any]:
        return self.client.get_tagged_media()

    def get_mentions(self) -> Dict[str, Any]:
        return self.client.get_mentions()

    def get_mention_media(self, media_id: str, mentioned_media_id: str) -> Dict[str, Any]:
        return self.client.get_mention_media(media_id, mentioned_media_id)

    # ---------------------------------------------------------------
    # 🔍 BUSINESS DISCOVERY
    # ---------------------------------------------------------------

    def discover_business_account(self, username: str) -> Dict[str, Any]:
        return self.client.discover_business_account(username)

    def discover_business_media(self, username: str) -> Dict[str, Any]:
        return self.client.discover_business_media(username)

    # ---------------------------------------------------------------
    # 💌 MESSAGING
    # ---------------------------------------------------------------

    def get_conversations(self) -> Dict[str, Any]:
        return self.client.get_conversations()

    def get_conversation_messages(self, conversation_id: str) -> Dict[str, Any]:
        return self.client.get_conversation_messages(conversation_id)

    def send_message(self, recipient_id: str, message_text: str) -> Dict[str, Any]:
        return self.client.send_message(recipient_id, message_text)

    def send_image_message(self, recipient_id: str, image_url: str) -> Dict[str, Any]:
        return self.client.send_image_message(recipient_id, image_url)

    # ---------------------------------------------------------------
    # 📡 LIVE VIDEO
    # ---------------------------------------------------------------

    def create_live_media(self, title: str = "") -> Dict[str, Any]:
        return self.client.create_live_media(title)

    def get_live_media(self, live_video_id: str) -> Dict[str, Any]:
        return self.client.get_live_media(live_video_id)

    def end_live_media(self, live_video_id: str) -> Dict[str, Any]:
        return self.client.end_live_media(live_video_id)

    # ---------------------------------------------------------------
    # 📌 SAVED MEDIA
    # ---------------------------------------------------------------

    def get_saved_media(self) -> Dict[str, Any]:
        return self.client.get_saved_media()

    # ---------------------------------------------------------------
    # 🛍️  PRODUCT TAGGING
    # ---------------------------------------------------------------

    def get_product_catalog(self) -> Dict[str, Any]:
        return self.client.get_product_catalog()

    def create_product_tagged_container(
        self, image_url: str, caption: str, product_tags: List[Dict]
    ) -> Dict[str, Any]:
        return self.client.create_product_tagged_container(image_url, caption, product_tags)


# ===================================================================
# Singleton
# ===================================================================
_instance = InstagramTools()


# ===================================================================
# ✅ EXISTING TOOLS (unchanged)
# ===================================================================

@tool
def get_instagram_profile():
    """Fetch the authenticated Instagram Business/Creator account profile."""
    return _instance.get_profile()


@tool
def get_instagram_media_list():
    """List all media posts for the authenticated account."""
    return _instance.get_media_list()


@tool
def get_instagram_media_details(media_id: str):
    """Get full details for a single media post by its ID."""
    return _instance.get_media_details(media_id)


@tool
def get_instagram_comments(media_id: str):
    """Retrieve all comments on a specific media post."""
    return _instance.get_comments(media_id)


@tool
def reply_to_instagram_comment(comment_id: str, message: str):
    """Reply to an existing comment on a media post."""
    return _instance.reply_to_comment(comment_id, message)


@tool
def get_instagram_account_insights(period: str = "day"):
    """
    Fetch account-level insights (impressions, reach, profile views).

    Args:
        period: "day", "week", or "days_28"
    """
    return _instance.get_account_insights(period)


@tool
def get_instagram_media_insights(media_id: str):
    """Fetch engagement metrics for a specific media post."""
    return _instance.get_media_insights(media_id)


@tool
def create_instagram_media_container(image_url: str, caption: str):
    """Create a photo media container (step 1 of 2-step publish)."""
    return _instance.create_media_container(image_url, caption)


@tool
def publish_instagram_media(creation_id: str):
    """Publish a previously created media container (step 2 of 2-step publish)."""
    return _instance.publish_media(creation_id)


@tool
def publish_instagram_post(image_url: str, caption: str):
    """One-shot: create and publish a photo post to Instagram."""
    return _instance.publish_post(image_url, caption)


# ===================================================================
# 🆕 COMMENT MANAGEMENT
# ===================================================================

@tool
def post_instagram_comment(media_id: str, message: str):
    """Post a new top-level comment on a media post."""
    return _instance.post_comment(media_id, message)


@tool
def hide_instagram_comment(comment_id: str, hide: bool = True):
    """
    Hide or unhide a comment.

    Args:
        comment_id: The comment to hide/unhide
        hide: True to hide, False to unhide
    """
    return _instance.hide_comment(comment_id, hide)


@tool
def delete_instagram_comment(comment_id: str):
    """Permanently delete a comment from a media post."""
    return _instance.delete_comment(comment_id)


# ===================================================================
# 🆕 EXTENDED INSIGHTS
# ===================================================================

@tool
def get_instagram_follower_demographics():
    """Fetch audience demographics: age, gender, city, country breakdown."""
    return _instance.get_follower_demographics()


@tool
def get_instagram_online_followers():
    """Fetch hourly breakdown of when your followers are online."""
    return _instance.get_online_followers()


# ===================================================================
# 🆕 VIDEO / REEL PUBLISHING
# ===================================================================

@tool
def create_instagram_video_container(
    video_url: str,
    caption: str,
    media_type: str = "REELS",
    thumb_offset: Optional[int] = None,
    share_to_feed: bool = True,
):
    """
    Create a video or Reel media container.

    Args:
        video_url: Publicly accessible video URL
        caption: Caption text
        media_type: "REELS" (default) or "VIDEO"
        thumb_offset: Millisecond offset for thumbnail frame
        share_to_feed: Whether to share Reel to main feed
    """
    return _instance.create_video_container(
        video_url, caption, media_type, thumb_offset, share_to_feed
    )


@tool
def check_instagram_container_status(container_id: str):
    """
    Poll the processing status of a video/reel container.
    Returns status_code: EXPIRED | ERROR | FINISHED | IN_PROGRESS | PUBLISHED
    """
    return _instance.check_container_status(container_id)


@tool
def publish_instagram_reel(video_url: str, caption: str):
    """One-shot: create and publish an Instagram Reel."""
    return _instance.publish_reel(video_url, caption)


# ===================================================================
# 🆕 CAROUSEL PUBLISHING
# ===================================================================

@tool
def create_instagram_carousel_item(
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
):
    """
    Create a single carousel item container.
    Provide either image_url or video_url.
    """
    return _instance.create_carousel_item(image_url, video_url)


@tool
def create_instagram_carousel_container(children_ids: List[str], caption: str):
    """
    Create a carousel post container from a list of item container IDs.

    Args:
        children_ids: List of item container IDs (2–10 items)
        caption: Caption for the carousel
    """
    return _instance.create_carousel_container(children_ids, caption)


@tool
def publish_instagram_carousel(image_urls: List[str], caption: str):
    """
    One-shot: upload 2–10 images as carousel items and publish.

    Args:
        image_urls: List of public image URLs (2–10)
        caption: Caption for the carousel post
    """
    return _instance.publish_carousel(image_urls, caption)


# ===================================================================
# 🆕 STORIES
# ===================================================================

@tool
def create_instagram_story_container(
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
):
    """Create a Story media container. Provide image_url or video_url."""
    return _instance.create_story_container(image_url, video_url)


@tool
def publish_instagram_story(
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
):
    """One-shot: create and publish an Instagram Story."""
    return _instance.publish_story(image_url, video_url)


@tool
def get_instagram_stories():
    """Retrieve currently active Stories for the account."""
    return _instance.get_stories()


# ===================================================================
# 🆕 HASHTAG SEARCH
# ===================================================================

@tool
def search_instagram_hashtag(hashtag: str):
    """
    Look up the ID for an Instagram hashtag (no # symbol needed).

    Args:
        hashtag: e.g. "travel"
    """
    return _instance.search_hashtag(hashtag)


@tool
def get_instagram_hashtag_top_media(hashtag_id: str):
    """Fetch top-performing media for a hashtag ID."""
    return _instance.get_hashtag_top_media(hashtag_id)


@tool
def get_instagram_hashtag_recent_media(hashtag_id: str):
    """Fetch recently published media for a hashtag ID."""
    return _instance.get_hashtag_recent_media(hashtag_id)


@tool
def search_instagram_hashtag_media(hashtag: str, top: bool = True):
    """
    One-shot: search hashtag then return top or recent media.

    Args:
        hashtag: Hashtag without # (e.g. "travel")
        top: True for top media, False for recent
    """
    return _instance.search_hashtag_media(hashtag, top)


@tool
def get_instagram_recently_searched_hashtags():
    """Return hashtags searched by this account in the last 7 days (max 30/week)."""
    return _instance.get_recently_searched_hashtags()


# ===================================================================
# 🆕 MENTIONS & TAGGED MEDIA
# ===================================================================

@tool
def get_instagram_tagged_media():
    """Retrieve posts in which this account has been tagged by others."""
    return _instance.get_tagged_media()


@tool
def get_instagram_mentions():
    """Retrieve media and comments where this account has been @mentioned."""
    return _instance.get_mentions()


@tool
def get_instagram_mention_media(media_id: str, mentioned_media_id: str):
    """
    Get details of a media post where this account was @mentioned in the caption.

    Args:
        media_id: Media ID of the post with the mention
        mentioned_media_id: The mentioned_media_id from a mention webhook event
    """
    return _instance.get_mention_media(media_id, mentioned_media_id)


# ===================================================================
# 🆕 BUSINESS DISCOVERY
# ===================================================================

@tool
def discover_instagram_business_account(username: str):
    """
    Look up the public profile of another Business/Creator account by username.

    Args:
        username: Target Instagram username (no @ symbol)
    """
    return _instance.discover_business_account(username)


@tool
def discover_instagram_business_media(username: str):
    """
    Retrieve the recent media of another public Business/Creator account.

    Args:
        username: Target Instagram username
    """
    return _instance.discover_business_media(username)


# ===================================================================
# 🆕 MESSAGING (DIRECT MESSAGES)
# ===================================================================

@tool
def get_instagram_conversations():
    """Fetch all DM conversations for the Instagram account."""
    return _instance.get_conversations()


@tool
def get_instagram_conversation_messages(conversation_id: str):
    """
    Retrieve messages from a specific DM conversation.

    Args:
        conversation_id: Conversation ID from get_instagram_conversations
    """
    return _instance.get_conversation_messages(conversation_id)


@tool
def send_instagram_message(recipient_id: str, message_text: str):
    """
    Send a text DM to an Instagram user.

    Args:
        recipient_id: Instagram-scoped user ID (IGSID) of the recipient
        message_text: Text content to send
    """
    return _instance.send_message(recipient_id, message_text)


@tool
def send_instagram_image_message(recipient_id: str, image_url: str):
    """
    Send an image attachment via DM.

    Args:
        recipient_id: Instagram-scoped user ID (IGSID) of the recipient
        image_url: Publicly accessible image URL
    """
    return _instance.send_image_message(recipient_id, image_url)


# ===================================================================
# 🆕 LIVE VIDEO
# ===================================================================

@tool
def create_instagram_live(title: str = ""):
    """
    Create a live video broadcast object.

    Args:
        title: Optional broadcast title
    """
    return _instance.create_live_media(title)


@tool
def get_instagram_live(live_video_id: str):
    """
    Fetch status and details of an active or completed live broadcast.

    Args:
        live_video_id: Live video media ID
    """
    return _instance.get_live_media(live_video_id)


@tool
def end_instagram_live(live_video_id: str):
    """
    End an active Instagram Live broadcast.

    Args:
        live_video_id: Live video media ID
    """
    return _instance.end_live_media(live_video_id)


# ===================================================================
# 🆕 SAVED MEDIA
# ===================================================================

@tool
def get_instagram_saved_media():
    """Retrieve media saved/bookmarked by this account."""
    return _instance.get_saved_media()


# ===================================================================
# 🆕 PRODUCT TAGGING (Shopping)
# ===================================================================

@tool
def get_instagram_product_catalog():
    """Retrieve the product catalog linked to this Instagram Shopping account."""
    return _instance.get_product_catalog()


@tool
def create_instagram_product_tagged_post(
    image_url: str,
    caption: str,
    product_tags: List[Dict],
):
    """
    Create a shoppable post container with product tags.

    Args:
        image_url: Public image URL
        caption: Caption text
        product_tags: List of dicts with keys:
                      product_id (str), merchant_id (str),
                      x (float 0.0–1.0), y (float 0.0–1.0)
    """
    return _instance.create_product_tagged_container(image_url, caption, product_tags)
