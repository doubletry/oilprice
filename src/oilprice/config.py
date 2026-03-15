"""配置管理模块 - 从 .env 文件加载配置"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    """应用配置，所有字段从环境变量加载"""

    corp_id: str
    secret: str
    agent_id: str
    user_ids: list[str]
    province: str = "guangdong"


def load_config(env_path: str | None = None) -> Config:
    """从 .env 文件加载配置

    Args:
        env_path: .env 文件路径，默认为项目根目录下的 .env

    Returns:
        Config 实例

    Raises:
        ValueError: 缺少必需的配置项时抛出
    """
    if env_path:
        load_dotenv(env_path, override=True)
    else:
        # 优先从当前工作目录查找 .env（兼容打包后的可执行文件）
        # 其次从项目源码目录查找
        cwd_env = Path.cwd() / ".env"
        src_env = Path(__file__).parent.parent.parent / ".env"
        load_dotenv(cwd_env if cwd_env.exists() else src_env, override=True)

    missing = []
    corp_id = os.getenv("CORP_ID", "")
    secret = os.getenv("SECRET", "")
    agent_id = os.getenv("AGENT_ID", "")
    user_ids_str = os.getenv("USER_IDS", "")

    if not corp_id:
        missing.append("CORP_ID")
    if not secret:
        missing.append("SECRET")
    if not agent_id:
        missing.append("AGENT_ID")
    if not user_ids_str:
        missing.append("USER_IDS")

    if missing:
        raise ValueError(f"缺少必需的环境变量: {', '.join(missing)}")

    user_ids = [uid.strip() for uid in user_ids_str.split(",") if uid.strip()]
    province = os.getenv("PROVINCE", "guangdong").strip()

    return Config(
        corp_id=corp_id,
        secret=secret,
        agent_id=agent_id,
        user_ids=user_ids,
        province=province,
    )
