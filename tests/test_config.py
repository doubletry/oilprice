"""配置模块测试"""

import os

import pytest

from oilprice.config import Config, load_config


class TestLoadConfig:
    """测试 load_config 函数"""

    def test_load_from_env_file(self, tmp_path):
        """从 .env 文件加载配置"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "CORP_ID=test_corp\n"
            "SECRET=test_secret\n"
            "AGENT_ID=1000001\n"
            "USER_IDS=user1,user2\n"
            "PROVINCE=beijing\n"
        )
        config = load_config(str(env_file))
        assert config.corp_id == "test_corp"
        assert config.secret == "test_secret"
        assert config.agent_id == "1000001"
        assert config.user_ids == ["user1", "user2"]
        assert config.province == "beijing"

    def test_missing_required_fields(self, tmp_path, monkeypatch):
        """缺少必需字段时抛出 ValueError"""
        # 清除所有可能存在的环境变量
        for key in ["CORP_ID", "SECRET", "AGENT_ID", "USER_IDS"]:
            monkeypatch.delenv(key, raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text("PROVINCE=guangdong\n")
        with pytest.raises(ValueError, match="CORP_ID"):
            load_config(str(env_file))

    def test_default_province(self, tmp_path):
        """省份默认值为 guangdong"""
        env_file = tmp_path / ".env"
        env_file.write_text("CORP_ID=test\nSECRET=test\nAGENT_ID=1\nUSER_IDS=user1\n")
        config = load_config(str(env_file))
        assert config.province == "guangdong"

    def test_user_ids_single(self, tmp_path):
        """单个用户 ID"""
        env_file = tmp_path / ".env"
        env_file.write_text("CORP_ID=test\nSECRET=test\nAGENT_ID=1\nUSER_IDS=user1\n")
        config = load_config(str(env_file))
        assert config.user_ids == ["user1"]

    def test_user_ids_with_spaces(self, tmp_path):
        """用户 ID 列表含空格时自动去除"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "CORP_ID=test\nSECRET=test\nAGENT_ID=1\nUSER_IDS= user1 , user2 ,user3\n"
        )
        config = load_config(str(env_file))
        assert config.user_ids == ["user1", "user2", "user3"]

    def test_default_prediction_mode(self, tmp_path):
        """预测模式默认值为 fallback"""
        env_file = tmp_path / ".env"
        env_file.write_text("CORP_ID=test\nSECRET=test\nAGENT_ID=1\nUSER_IDS=user1\n")
        config = load_config(str(env_file))
        assert config.prediction_mode == "fallback"

    def test_prediction_mode_custom(self, tmp_path):
        """设置预测模式为 custom"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "CORP_ID=test\nSECRET=test\nAGENT_ID=1\nUSER_IDS=user1\n"
            "PREDICTION_MODE=custom\n"
        )
        config = load_config(str(env_file))
        assert config.prediction_mode == "custom"

    def test_prediction_mode_both(self, tmp_path):
        """设置预测模式为 both"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "CORP_ID=test\nSECRET=test\nAGENT_ID=1\nUSER_IDS=user1\n"
            "PREDICTION_MODE=both\n"
        )
        config = load_config(str(env_file))
        assert config.prediction_mode == "both"

    def test_prediction_mode_qiyoujiage(self, tmp_path):
        """设置预测模式为 qiyoujiage"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "CORP_ID=test\nSECRET=test\nAGENT_ID=1\nUSER_IDS=user1\n"
            "PREDICTION_MODE=qiyoujiage\n"
        )
        config = load_config(str(env_file))
        assert config.prediction_mode == "qiyoujiage"

    def test_prediction_mode_case_insensitive(self, tmp_path):
        """预测模式不区分大小写"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "CORP_ID=test\nSECRET=test\nAGENT_ID=1\nUSER_IDS=user1\n"
            "PREDICTION_MODE=Both\n"
        )
        config = load_config(str(env_file))
        assert config.prediction_mode == "both"

    def test_prediction_mode_invalid_falls_back(self, tmp_path):
        """无效的预测模式回退为 fallback"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "CORP_ID=test\nSECRET=test\nAGENT_ID=1\nUSER_IDS=user1\n"
            "PREDICTION_MODE=invalid\n"
        )
        config = load_config(str(env_file))
        assert config.prediction_mode == "fallback"
