import yaml
from loguru import logger

from .parse_html import parse_oil_price
from .wechat_notify import send_wechat_message


def send_oilprice_message(config):

    try:
        url = config["url"]
        user_ids = config["user_ids"]
    except Exception as e:
        logger.error(f"配置文件错误: {e}")

    corp_id = config.get("corp_id")
    secret = config.get("secret")
    agent_id = config.get("agent_id")

    data = parse_oil_price(url)
    if data:
        title = data["title"]
        content = data["content"]
        send_wechat_message(user_ids, title, content, corp_id, secret, agent_id)


if __name__ == "__main__":

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    send_oilprice_message(config)
