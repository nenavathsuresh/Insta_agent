from fastmcp.tools import tool
from mcp_server.utils.instagram_client import InstagramClient
import time
import random
from typing import Any, Dict


class InstagramTools:
    def __init__(self):
        self.client = InstagramClient()
        self.last_post_time = 0

    def get_profile(self) -> Dict[str, Any]:
        return self.client.get_profile()

    def get_media_list(self) -> Dict[str, Any]:
        return self.client.get_media_list()

    def get_media_details(self, media_id: str) -> Dict[str, Any]:
        return self.client.get_media_details(media_id)

    def get_comments(self, media_id: str) -> Dict[str, Any]:
        return self.client.get_comments(media_id)

    def reply_to_comment(self, comment_id: str, message: str) -> Dict[str, Any]:
        return self.client.reply_to_comment(comment_id, message)

    def get_account_insights(self) -> Dict[str, Any]:
        return self.client.get_account_insights()

    def get_media_insights(self, media_id: str) -> Dict[str, Any]:
        return self.client.get_media_insights(media_id)

    def create_media_container(self, image_url: str, caption: str) -> Dict[str, Any]:
        return self.client.create_media_container(image_url, caption)

    def publish_media(self, creation_id: str) -> Dict[str, Any]:
        current_time = time.time()

        if current_time - self.last_post_time < 60:
            raise Exception("Rate limit: wait before posting again")

        response = self.client.publish_media(creation_id)
        self.last_post_time = current_time
        return response

    def publish_post(self, image_url: str, caption: str) -> Dict[str, Any]:
        current_time = time.time()

        if current_time - self.last_post_time < 60:
            raise Exception("Rate limit: wait before posting again")

        time.sleep(random.randint(5, 15))

        response = self.client.publish_post(image_url, caption)
        self.last_post_time = current_time
        return response


_instance = InstagramTools()


@tool
def get_instagram_profile():
    return _instance.get_profile()


@tool
def get_instagram_media_list():
    return _instance.get_media_list()


@tool
def get_instagram_media_details(media_id: str):
    return _instance.get_media_details(media_id)


@tool
def get_instagram_comments(media_id: str):
    return _instance.get_comments(media_id)


@tool
def reply_to_instagram_comment(comment_id: str, message: str):
    return _instance.reply_to_comment(comment_id, message)


@tool
def get_instagram_account_insights():
    return _instance.get_account_insights()


@tool
def get_instagram_media_insights(media_id: str):
    return _instance.get_media_insights(media_id)


@tool
def create_instagram_media_container(image_url: str, caption: str):
    return _instance.create_media_container(image_url, caption)


@tool
def publish_instagram_media(creation_id: str):
    return _instance.publish_media(creation_id)


@tool
def publish_instagram_post(image_url: str, caption: str):
    return _instance.publish_post(image_url, caption)
