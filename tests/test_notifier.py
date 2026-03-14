"""通知模块测试"""

from unittest.mock import MagicMock, patch

from oilprice.notifier import send_wechat_message


class TestSendWechatMessage:
    """测试企业微信消息发送"""

    @patch("oilprice.notifier.WeChatClient")
    def test_send_success(self, mock_client_cls):
        """成功发送消息"""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.message.send_text_card.return_value = {"errcode": 0, "errmsg": "ok"}

        result = send_wechat_message(
            corp_id="test_corp",
            secret="test_secret",
            agent_id="1000001",
            user_ids=["user1", "user2"],
            title="测试标题",
            description="测试内容",
        )

        assert result is True
        mock_client_cls.assert_called_once_with("test_corp", "test_secret")
        mock_client.message.send_text_card.assert_called_once_with(
            "1000001",
            "user1|user2",
            title="测试标题",
            description="测试内容",
            url="https://www.autohome.com.cn/oil/",
            btntxt="查看详情",
        )

    @patch("oilprice.notifier.WeChatClient")
    def test_send_failure(self, mock_client_cls):
        """发送失败返回 False"""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.message.send_text_card.side_effect = Exception("API error")

        result = send_wechat_message(
            corp_id="test_corp",
            secret="test_secret",
            agent_id="1000001",
            user_ids=["user1"],
            title="测试",
            description="测试",
        )

        assert result is False

    @patch("oilprice.notifier.WeChatClient")
    def test_single_user(self, mock_client_cls):
        """单用户消息发送"""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.message.send_text_card.return_value = {"errcode": 0}

        send_wechat_message(
            corp_id="c", secret="s", agent_id="1",
            user_ids=["only_user"],
            title="t", description="d",
        )

        call_args = mock_client.message.send_text_card.call_args
        assert call_args[0][1] == "only_user"  # user_ids_str
