"""
WebSocketチャンネル管理 - リアルタイム通信インフラ
"""
import json
from typing import Any, Dict, Optional

from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend

import config
from infrastructure.logger import get_logger

logger = get_logger("infrastructure.channels")

class ChannelPublisher:
    """WebSocketチャンネルへのメッセージ発行を管理"""

    def __init__(self, channels_plugin: ChannelsPlugin):
        self.logger = get_logger("infrastructure.ChannelPublisher")
        self.channels_plugin = channels_plugin
        self.channel_name = config.WS_CHANNEL_NAME
        self.logger.info(f"ChannelPublisher初期化: チャンネル名={self.channel_name}")

    def publish_update(self, image_path: str) -> None:
        """モザイク更新通知をチャンネルに発行"""
        try:
            message = json.dumps({
                "action": "mosaic_updated",
                "path": image_path
            })
            self.logger.info(f"モザイク更新通知: {image_path}")
            self.logger.debug(f"メッセージ内容: {message}")
            self.channels_plugin.publish(message, self.channel_name)
            self.logger.debug("メッセージ発行完了")
        except Exception as e:
            self.logger.error(f"メッセージ発行エラー: {str(e)}", exc_info=True)

    def publish_message(self, message_type: str, data: Dict[str, Any]) -> None:
        """汎用メッセージをチャンネルに発行"""
        try:
            message = json.dumps({
                "type": message_type,
                "data": data
            })
            self.logger.info(f"メッセージ発行: タイプ={message_type}")
            self.logger.debug(f"メッセージ内容: {message}")
            self.channels_plugin.publish(message, self.channel_name)
            self.logger.debug("メッセージ発行完了")
        except Exception as e:
            self.logger.error(f"メッセージ発行エラー: {str(e)}", exc_info=True)


def create_channels_plugin() -> ChannelsPlugin:
    """チャンネルプラグインを初期化"""
    try:
        logger.info(f"チャンネルプラグイン初期化: チャンネル名={config.WS_CHANNEL_NAME}")
        plugin = ChannelsPlugin(
            backend=MemoryChannelsBackend(history=config.WS_HISTORY_SIZE),
            channels=[config.WS_CHANNEL_NAME],
            ws_handler_send_history=config.WS_SEND_HISTORY,
        )
        logger.info("チャンネルプラグイン初期化完了")
        return plugin
    except Exception as e:
        logger.error(f"チャンネルプラグイン初期化エラー: {str(e)}", exc_info=True)
        raise
