from mcp_server.tools.instagram_tools import (
    get_instagram_profile,
    get_instagram_media_list,
    get_instagram_media_details,
    get_instagram_comments,
    reply_to_instagram_comment,
    get_instagram_account_insights,
    get_instagram_media_insights,
    create_instagram_media_container,
    publish_instagram_media,
    publish_instagram_post
)


def register_tools(mcp):
    mcp.add_tool(get_instagram_profile)
    mcp.add_tool(get_instagram_media_list)
    mcp.add_tool(get_instagram_media_details)
    mcp.add_tool(get_instagram_comments)
    mcp.add_tool(reply_to_instagram_comment)
    mcp.add_tool(get_instagram_account_insights)
    mcp.add_tool(get_instagram_media_insights)
    mcp.add_tool(create_instagram_media_container)
    mcp.add_tool(publish_instagram_media)
    mcp.add_tool(publish_instagram_post)
