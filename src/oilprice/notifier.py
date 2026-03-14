"""企业微信消息推送模块"""

from loguru import logger
from wechatpy.enterprise import WeChatClient

# 消息中"查看详情"按钮的跳转链接
OIL_DETAIL_URL = "https://www.autohome.com.cn/oil/"


def send_wechat_message(
    corp_id: str,
    secret: str,
    agent_id: str,
    user_ids: list[str],
    title: str,
    description: str,
) -> bool:
    """通过企业微信应用推送文本卡片消息

    Args:
        corp_id: 企业微信 Corp ID
        secret: 应用 Secret
        agent_id: 应用 Agent ID
        user_ids: 接收消息的用户 ID 列表
        title: 卡片标题
        description: 卡片描述内容

    Returns:
        发送成功返回 True，失败返回 False
    """
    try:
        client = WeChatClient(corp_id, secret)
        user_ids_str = "|".join(user_ids)

        response = client.message.send_text_card(
            agent_id,
            user_ids_str,
            title=title,
            description=description,
            url=OIL_DETAIL_URL,
            btntxt="查看详情",
        )
        logger.info(f"消息发送成功: {response}")
        return True

    except Exception as e:
        logger.exception(f"消息发送失败: {e}")
        return False
