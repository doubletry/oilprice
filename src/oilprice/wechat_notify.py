import os

from loguru import logger
from wechatpy.enterprise import WeChatClient



def send_wechat_message(
    user_ids, title, content=None, corp_id=None, secret=None, agent_id=None
):


    if not corp_id or not secret or not agent_id:
        corp_id = os.getenv("CORP_ID")
        secret = os.getenv("SECRET")
        agent_id = os.getenv("AGENT_ID")

    client = WeChatClient(corp_id, secret)

    if isinstance(user_ids, list):
        user_ids = "|".join(user_ids)

        try:
            response = client.message.send_text_card(
                agent_id,
                user_ids,
                title=title,
                description=content,
                url="https://www.autohome.com.cn/oil/",
                btntxt="查看详情",
            )
            # response = client.message.send_text(agent_id, user_id, content)
            logger.info(f"消息发送成功: {response}")
        except Exception as e:
            logger.exception(f"消息发送失败: {e}")
