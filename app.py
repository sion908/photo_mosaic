import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from litestar import Litestar
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.datastructures import State
from litestar.di import Provide
from litestar.static_files import create_static_files_router
from litestar.template.config import TemplateConfig

import config
from adapters.database import DatabaseManager, ImageRepository, SettingsRepository
from adapters.storage import FileStorage
from core.services import MosaicService
from infrastructure.auth import create_auth_middleware
from infrastructure.channels import ChannelPublisher, create_channels_plugin
from infrastructure.image_sync import ImageSyncService
from infrastructure.logger import get_logger, setup_logger
from interfaces.api.admin_routes import (
    admin_panel,
    reset_confirmation,
    reset_mosaic,
    update_settings,
)
from interfaces.api.routes import display, get_stats, index, upload_image
from interfaces.api.websockets import mosaic_ws_handler

# データベース関連の依存性注入
db_manager = DatabaseManager()

def provide_image_repository() -> ImageRepository:
    """ImageRepositoryを提供"""
    return ImageRepository(db_manager)

def provide_settings_repository() -> SettingsRepository:
    """SettingsRepositoryを提供"""
    return SettingsRepository(db_manager)

# ファイルストレージの依存性注入
def provide_file_storage() -> FileStorage:
    """FileStorageを提供"""
    return FileStorage()

# チャンネル関連の依存性注入
channels_plugin = create_channels_plugin()

def provide_channel_publisher() -> ChannelPublisher:
    """ChannelPublisherを提供"""
    return ChannelPublisher(channels_plugin)

# モザイクサービスの依存性注入 (app.stateを使用)
def provide_mosaic_service(
    image_repo: ImageRepository,
    file_storage: FileStorage,
    channel_publisher: ChannelPublisher,
    settings_repo: SettingsRepository,
    state: State
) -> MosaicService:
    """MosaicServiceを提供"""
    # stateにサービスがあればそれを返す
    if hasattr(state, "mosaic_service"):
        return state.mosaic_service
    
    # なければログを出力
    logger = get_logger("provide_mosaic_service")
    logger.info("新しいMosaicServiceインスタンスを作成します")
    
    # 新しいインスタンスを作成
    service = MosaicService(
        image_repo=image_repo,
        file_storage=file_storage,
        channel_publisher=channel_publisher,
        settings_repo=settings_repo
    )
    
    # 状態に保存
    state.mosaic_service = service
    return service

# 画像同期サービスの提供
def provide_image_sync_service(
    image_repo: ImageRepository
) -> ImageSyncService:
    """ImageSyncServiceを提供"""
    return ImageSyncService(image_repo)


# アプリケーションライフスパンのコンテキストマネージャー
@asynccontextmanager
async def app_lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    """アプリケーションのライフスパンを管理するコンテキストマネージャー"""
    logger = setup_logger(
        log_level=config.get_log_level(),
        log_dir=str(config.LOG_DIR)
    )
    logger.info("アプリケーション起動中...")
    
    try:
        # 必要なディレクトリを作成
        try:
            config.ensure_directories()
            logger.info("必要なディレクトリを作成しました")
        except Exception as e:
            logger.error(f"ディレクトリ作成エラー: {str(e)}", exc_info=True)

        # データベースを初期化
        try:
            logger.debug("データベース初期化を開始: %s", config.DB_PATH)
            db_manager.initialize()
            logger.info("データベース初期化完了")
        except Exception as e:
            logger.error(f"データベース初期化エラー: {str(e)}", exc_info=True)
        
        # 画像の同期処理を実行
        try:
            logger.info("画像同期処理を開始します")
            image_repo = provide_image_repository()
            image_sync_service = provide_image_sync_service(image_repo)
            
            processed_count, added_count, self_upload_count, error_count = await image_sync_service.sync_images()
            logger.info(f"画像同期完了: 処理={processed_count}, 追加={added_count}, self_uploads={self_upload_count}, エラー={error_count}")
            
            # 同期結果をstateに保存（再生成用）
            app.state.sync_results = {
                "processed": processed_count,
                "added": added_count,
                "self_upload": self_upload_count,
                "errors": error_count
            }
        except Exception as e:
            logger.error(f"画像同期エラー: {str(e)}", exc_info=True)
            app.state.sync_results = {"errors": 1}
        
        # MosaicServiceを初期化してstateに保存
        try:
            logger.info("MosaicServiceを初期化します")
            image_repo = provide_image_repository()
            file_storage = provide_file_storage()
            channel_publisher = provide_channel_publisher()
            settings_repo = provide_settings_repository()
            
            # サービスを作成して状態に保存
            app.state.mosaic_service = MosaicService(
                image_repo=image_repo,
                file_storage=file_storage,
                channel_publisher=channel_publisher,
                settings_repo=settings_repo
            )
            
            # 設定をロード
            await app.state.mosaic_service.load_settings()
            logger.info("MosaicService設定をロードしました")
            
            # 画像同期後にモザイクを再生成
            sync_results = getattr(app.state, "sync_results", {})
            need_regenerate = (
                sync_results.get("processed", 0) > 0 or 
                sync_results.get("added", 0) > 0 or 
                sync_results.get("self_upload", 0) > 0
            )
            
            if need_regenerate:
                logger.info("画像同期によってファイルが更新されたため、モザイクを再生成します")
                regenerated = await app.state.mosaic_service.regenerate_mosaic()
                logger.info(f"モザイク再生成結果: {regenerated}")
        except Exception as e:
            logger.error(f"MosaicService初期化エラー: {str(e)}", exc_info=True)
        
        logger.info(f"初期化完了！")
        
        # yieldで制御をLitestarフレームワークに渡す
        yield
        
        # シャットダウン時の処理
        logger.info("アプリケーションシャットダウン中...")
        
        # 必要に応じてここでリソースをクリーンアップ
        
        logger.info("アプリケーションを安全にシャットダウンしました")
        
    except Exception as e:
        logger.critical(f"ライフスパン処理中に予期しないエラーが発生しました: {str(e)}", exc_info=True)
        # エラーが発生してもyieldを実行して、フレームワークに制御を戻す
        yield
        logger.info("エラーが発生しましたが、アプリケーションはシャットダウンします")


# Basic認証ミドルウェア
auth_middleware = create_auth_middleware()

# アプリケーション設定
# メインアプリケーション
app = Litestar(
    route_handlers=[
        # APIルート
        index, display, upload_image, get_stats,
        # 管理者ルート
        admin_panel, update_settings, reset_confirmation, reset_mosaic,
        # WebSocketハンドラ
        mosaic_ws_handler,
        # 静的ファイルルーター
        create_static_files_router(path="/static", directories=["static"]),
        create_static_files_router(path="/uploads", directories=["uploads"])
    ],
    # テンプレート設定
    template_config=TemplateConfig(
        directory=Path("interfaces/web/templates"),
        engine=JinjaTemplateEngine,
    ),
    # プラグイン
    plugins=[channels_plugin],
    # lifespan コンテキストマネージャー
    lifespan=[app_lifespan],
    # 依存性注入 (同期関数の警告を抑制)
    dependencies={
        "image_repo": Provide(provide_image_repository, sync_to_thread=False),
        "settings_repo": Provide(provide_settings_repository, sync_to_thread=False),
        "file_storage": Provide(provide_file_storage, sync_to_thread=False),
        "channel_publisher": Provide(provide_channel_publisher, sync_to_thread=False),
        "mosaic_service": Provide(provide_mosaic_service, sync_to_thread=False),
    },
    # ミドルウェア
    middleware=[auth_middleware],
    # 初期状態を設定
    state=State({"initialized": True})
)


# アプリケーション実行
if __name__ == "__main__":
    import uvicorn

    # UvicornでLitestarアプリを起動
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
