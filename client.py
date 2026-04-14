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


def build_tool_call(
    action: str,
    media_id: str | None,
    comment_id: str | None,
    message: str | None,
    image_url: str | None,
    caption: str | None,
    creation_id: str | None,
) -> tuple[str, dict[str, Any]] | None:
    if action == "list":
        return None
    if action == "profile":
        return ("get_instagram_profile", {})
    if action == "media-list":
        return ("get_instagram_media_list", {})
    if action == "media-details":
        if not media_id:
            raise ValueError("media-details requires --media-id")
        return ("get_instagram_media_details", {"media_id": media_id})
    if action == "comments":
        if not media_id:
            raise ValueError("comments requires --media-id")
        return ("get_instagram_comments", {"media_id": media_id})
    if action == "reply-comment":
        if not comment_id or message is None:
            raise ValueError("reply-comment requires --comment-id and --message")
        return (
            "reply_to_instagram_comment",
            {"comment_id": comment_id, "message": message},
        )
    if action == "account-insights":
        return ("get_instagram_account_insights", {})
    if action == "media-insights":
        if not media_id:
            raise ValueError("media-insights requires --media-id")
        return ("get_instagram_media_insights", {"media_id": media_id})
    if action == "create-container":
        if not image_url or caption is None:
            raise ValueError("create-container requires --image-url and --caption")
        return (
            "create_instagram_media_container",
            {"image_url": image_url, "caption": caption},
        )
    if action == "publish-media":
        if not creation_id:
            raise ValueError("publish-media requires --creation-id")
        return ("publish_instagram_media", {"creation_id": creation_id})
    if action == "publish":
        if not image_url or caption is None:
            raise ValueError("publish requires --image-url and --caption")
        return (
            "publish_instagram_post",
            {"image_url": image_url, "caption": caption},
        )
    raise ValueError(f"Unsupported action: {action}")


async def run_client(
    action: str,
    media_id: str | None,
    comment_id: str | None,
    message: str | None,
    image_url: str | None,
    caption: str | None,
    creation_id: str | None,
    transport: str,
) -> None:
    if transport == "stdio":
        connection = SERVER_SCRIPT
    elif transport == "inprocess":
        connection = create_server().mcp
    else:
        raise ValueError(f"Unsupported transport: {transport}")

    try:
        async with Client(connection) as client:
            tools = await client.list_tools()
            print("Available tools:")
            for tool in tools:
                print(f"- {tool.name}")

            tool_call = build_tool_call(
                action,
                media_id,
                comment_id,
                message,
                image_url,
                caption,
                creation_id,
            )
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
        choices=[
            "list",
            "profile",
            "media-list",
            "media-details",
            "comments",
            "reply-comment",
            "account-insights",
            "media-insights",
            "create-container",
            "publish-media",
            "publish",
        ],
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
    parser.add_argument(
        "--transport",
        choices=["inprocess", "stdio"],
        default="inprocess",
        help="How to connect to the MCP server",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(
        run_client(
            args.action,
            args.media_id,
            args.comment_id,
            args.message,
            args.image_url,
            args.caption,
            args.creation_id,
            args.transport,
        )
    )


if __name__ == "__main__":
    main()
