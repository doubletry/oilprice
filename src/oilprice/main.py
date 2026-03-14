"""油价监控工具入口模块"""

from loguru import logger

from .config import Config, load_config
from .formatter import format_message, get_province_cn
from .notifier import send_wechat_message
from .scraper import scrape_oil_prices


def run(config: Config | None = None) -> bool:
    """执行完整的油价查询和推送流程

    Args:
        config: 配置对象，为 None 时自动从 .env 加载

    Returns:
        发送成功返回 True，失败返回 False
    """
    if config is None:
        config = load_config()

    # 1. 抓取油价数据
    logger.info("开始抓取油价数据...")
    data = scrape_oil_prices()

    # 2. 格式化消息
    province_cn = get_province_cn(config.province)
    title, description = format_message(data, province_cn)
    logger.info(f"标题: {title}")
    logger.info(f"内容:\n{description}")

    # 3. 推送到企业微信
    logger.info(f"正在推送消息给用户: {config.user_ids}")
    return send_wechat_message(
        corp_id=config.corp_id,
        secret=config.secret,
        agent_id=config.agent_id,
        user_ids=config.user_ids,
        title=title,
        description=description,
    )


def main():
    """CLI 入口函数"""
    import argparse

    parser = argparse.ArgumentParser(description="油价监控 - 查询实时油价并推送到企业微信")
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help=".env 配置文件路径（默认自动查找项目根目录）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅查询和格式化油价，不发送消息",
    )
    args = parser.parse_args()

    config = load_config(args.env)

    if args.dry_run:
        # 仅查询和展示，不推送
        data = scrape_oil_prices()
        province_cn = get_province_cn(config.province)
        title, description = format_message(data, province_cn)
        print(f"\n{'='*40}")
        print(f"标题: {title}")
        print(f"{'='*40}")
        print(description)
        print(f"{'='*40}\n")
    else:
        success = run(config)
        if not success:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
