"""
WebSocketハンドラ - リアルタイム通信のエンドポイント
"""
from litestar import WebSocket, websocket
from litestar.channels import ChannelsPlugin
from litestar.datastructures import State

import config
from infrastructure.logger import get_logger

logger = get_logger("api.websockets")

@websocket("/ws/mosaic")
async def mosaic_ws_handler(socket: WebSocket, channels: ChannelsPlugin) -> None:
    """
    モザイク更新用WebSocketハンドラ
    クライアントが接続するとモザイク更新通知を受け取る
    """
    client_id = f"{socket.client.host}:{socket.client.port}"
    logger.info(f"WebSocket接続リクエスト: {client_id}")

    # WebSocket接続を受け入れ
    try:
        await socket.accept()
        logger.info(f"WebSocket接続確立: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket接続確立エラー: {str(e)}", exc_info=True)
        return

    try:
        # チャンネルを購読開始
        async with channels.start_subscription([config.WS_CHANNEL_NAME]) as subscriber:
            logger.debug(f"チャンネル購読開始: {config.WS_CHANNEL_NAME}")

            # 接続直後に履歴を取得して送信
            await channels.put_subscriber_history(
                subscriber,
                [config.WS_CHANNEL_NAME],
                limit=config.WS_SEND_HISTORY
            )

            # バックグラウンドでメッセージ処理を開始
            async with subscriber.run_in_background(socket.send_text):
                logger.debug(f"バックグラウンドメッセージ処理開始: {client_id}")

                # クライアントからのメッセージを待機
                while True:
                    data = await socket.receive_text()
                    logger.debug(f"クライアントからのメッセージ受信: {data[:100]}...")

    except Exception as e:
        logger.error(f"WebSocketエラー: {str(e)}", exc_info=True)
        # 接続が既に閉じられていない場合は閉じる
        try:
            await socket.close(code=1011, reason=str(e))
            logger.info(f"WebSocket接続クローズ: {client_id}, 理由: {str(e)}")
        except Exception as close_error:
            logger.warning(f"WebSocket接続クローズ失敗: {str(close_error)}")
