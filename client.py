import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError

from app.server.mcp_server import create_server


ROOT = Path(__file__).resolve().parent
SERVER_SCRIPT = ROOT / "main.py"


ACTION_TO_TOOL = {
    "profile": ("get_instagram_profile", []),
    "media-list": ("get_instagram_media_list", []),
    "media-details": ("get_instagram_media_details", ["media_id"]),
    "comments": ("get_instagram_comments", ["media_id"]),
    "reply-comment": ("reply_to_instagram_comment", ["comment_id", "message"]),
    "account-insights": ("get_instagram_account_insights", []),
    "media-insights": ("get_instagram_media_insights", ["media_id"]),
    "create-container": ("create_instagram_media_container", ["image_url", "caption"]),
    "publish-media": ("publish_instagram_media", ["creation_id"]),
    "publish": ("publish_instagram_post", ["image_url", "caption"]),
    "post-comment": ("post_instagram_comment", ["media_id", "message"]),
    "hide-comment": ("hide_instagram_comment", ["comment_id", "hide"]),
    "delete-comment": ("delete_instagram_comment", ["comment_id"]),
    "follower-demographics": ("get_instagram_follower_demographics", []),
    "online-followers": ("get_instagram_online_followers", []),
    "create-video-container": (
        "create_instagram_video_container",
        ["video_url", "caption", "media_type", "thumb_offset", "share_to_feed"],
    ),
    "container-status": ("check_instagram_container_status", ["container_id"]),
    "publish-reel": ("publish_instagram_reel", ["video_url", "caption"]),
    "create-carousel-item": ("create_instagram_carousel_item", ["image_url", "video_url"]),
    "create-carousel-container": (
        "create_instagram_carousel_container",
        ["children_ids", "caption"],
    ),
    "publish-carousel": ("publish_instagram_carousel", ["image_urls", "caption"]),
    "create-story-container": ("create_instagram_story_container", ["image_url", "video_url"]),
    "publish-story": ("publish_instagram_story", ["image_url", "video_url"]),
    "stories": ("get_instagram_stories", []),
    "search-hashtag": ("search_instagram_hashtag", ["hashtag"]),
    "hashtag-top-media": ("get_instagram_hashtag_top_media", ["hashtag_id"]),
    "hashtag-recent-media": ("get_instagram_hashtag_recent_media", ["hashtag_id"]),
    "search-hashtag-media": ("search_instagram_hashtag_media", ["hashtag", "top"]),
    "recent-hashtags": ("get_instagram_recently_searched_hashtags", []),
    "tagged-media": ("get_instagram_tagged_media", []),
    "mentions": ("get_instagram_mentions", []),
    "mention-media": ("get_instagram_mention_media", ["media_id", "mentioned_media_id"]),
    "discover-business-account": ("discover_instagram_business_account", ["username"]),
    "discover-business-media": ("discover_instagram_business_media", ["username"]),
    "conversations": ("get_instagram_conversations", []),
    "conversation-messages": ("get_instagram_conversation_messages", ["conversation_id"]),
    "send-message": ("send_instagram_message", ["recipient_id", "message_text"]),
    "send-image-message": ("send_instagram_image_message", ["recipient_id", "image_url"]),
    "create-live": ("create_instagram_live", ["title"]),
    "get-live": ("get_instagram_live", ["live_video_id"]),
    "end-live": ("end_instagram_live", ["live_video_id"]),
    "saved-media": ("get_instagram_saved_media", []),
    "product-catalog": ("get_instagram_product_catalog", []),
    "create-product-tagged-post": (
        "create_instagram_product_tagged_post",
        ["image_url", "caption", "product_tags"],
    ),
}


def _get_arg_value(args: argparse.Namespace, name: str) -> Any:
    value = getattr(args, name)
    if value is None:
        raise ValueError(f"{args.action} requires --{name.replace('_', '-')}")
    return value


def build_tool_call(args: argparse.Namespace) -> tuple[str, dict[str, Any]] | None:
    if args.action == "list":
        return None

    tool_name, required_args = ACTION_TO_TOOL[args.action]
    payload = {name: _get_arg_value(args, name) for name in required_args}
    return tool_name, payload


async def run_client(args: argparse.Namespace) -> None:
    if args.transport == "stdio":
        connection = SERVER_SCRIPT
    elif args.transport == "inprocess":
        connection = create_server().mcp
    else:
        raise ValueError(f"Unsupported transport: {args.transport}")

    try:
        async with Client(connection) as client:
            tools = await client.list_tools()
            print("Available tools:")
            for tool in tools:
                print(f"- {tool.name}")

            tool_call = build_tool_call(args)
            if tool_call is None:
                return

            tool_name, arguments = tool_call
            result = await client.call_tool(tool_name, arguments)
            print("\nTool result:")
            print(json.dumps(result.data, indent=2))
            return
    except ToolError as exc:
        print("\nTool call failed.")
        print(str(exc).split("access_token=")[0].strip())
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local MCP client for Social MCP Server")
    parser.add_argument(
        "action",
        choices=["list", *ACTION_TO_TOOL.keys()],
        nargs="?",
        default="list",
        help="Which MCP action to run",
    )
    parser.add_argument("--media-id")
    parser.add_argument("--comment-id")
    parser.add_argument("--message")
    parser.add_argument("--image-url", dest="image_url")
    parser.add_argument("--caption")
    parser.add_argument("--creation-id")
    parser.add_argument("--hide", type=lambda value: value.lower() == "true")
    parser.add_argument("--video-url", dest="video_url")
    parser.add_argument("--media-type", dest="media_type", default="REELS")
    parser.add_argument("--thumb-offset", dest="thumb_offset", type=int)
    parser.add_argument("--share-to-feed", dest="share_to_feed", type=lambda value: value.lower() == "true", default=True)
    parser.add_argument("--container-id", dest="container_id")
    parser.add_argument("--children-ids", dest="children_ids", nargs="+")
    parser.add_argument("--image-urls", dest="image_urls", nargs="+")
    parser.add_argument("--hashtag")
    parser.add_argument("--hashtag-id", dest="hashtag_id")
    parser.add_argument("--top", type=lambda value: value.lower() == "true", default=True)
    parser.add_argument("--mentioned-media-id", dest="mentioned_media_id")
    parser.add_argument("--username")
    parser.add_argument("--conversation-id", dest="conversation_id")
    parser.add_argument("--recipient-id", dest="recipient_id")
    parser.add_argument("--message-text", dest="message_text")
    parser.add_argument("--title")
    parser.add_argument("--live-video-id", dest="live_video_id")
    parser.add_argument("--product-tags", dest="product_tags", type=json.loads)
    parser.add_argument(
        "--transport",
        choices=["inprocess", "stdio"],
        default="inprocess",
        help="How to connect to the MCP server",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_client(args))


if __name__ == "__main__":
    main()
