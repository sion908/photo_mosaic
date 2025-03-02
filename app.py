import logging
from pathlib import Path

from litestar import Litestar
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.datastructures import State
from litestar.di import Provide
from litestar.events import listener
from litestar.static_files import create_static_files_router
from litestar.template.config import TemplateConfig

import config
from adapters.database import DatabaseManager, ImageRepository, SettingsRepository
from adapters.storage import FileStorage
from core.services import MosaicService
from infrastructure.auth import create_auth_middleware
from infrastructure.channels import ChannelPublisher, create_channels_plugin
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

# モザイクサービスのシングルトンインスタンス
mosaic_service_instance = None

# モザイクサービスの依存性注入 (グローバル変数利用)
def provide_mosaic_service(
    image_repo: ImageRepository,
    file_storage: FileStorage,
    channel_publisher: ChannelPublisher,
    settings_repo: SettingsRepository
) -> MosaicService:
    """MosaicServiceを提供"""
    global mosaic_service_instance
    if mosaic_service_instance is None:
        logger = get_logger("app")
        logger.info("Creating new MosaicService instance")
        mosaic_service_instance = MosaicService(
            image_repo=image_repo,
            file_storage=file_storage,
            channel_publisher=channel_publisher,
            settings_repo=settings_repo
        )
    return mosaic_service_instance


# アプリケーション起動時の初期化処理
@listener("startup")
async def on_app_startup(app: Litestar) -> None:
    """アプリケーション起動時に実行される初期化コード"""
    # ロガーを初期化

    logger = setup_logger(
        log_level=config.get_log_level(),
        log_dir=str(config.LOG_DIR)
    )
    logger.info("アプリケーション起動中...")

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

        # テスト的にデータベースアクセス
        conn = db_manager.get_connection()
        cursor = conn.cursor()

        # テーブル一覧を確認
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.debug("DB内のテーブル: %s", [t[0] for t in tables])

        # settings テーブルがあれば内容を確認
        if ('settings',) in tables:
            cursor.execute("SELECT * FROM settings LIMIT 1")
            settings_row = cursor.fetchone()
            logger.debug("既存の設定: %s", settings_row)

        conn.close()
        logger.debug("DB接続テスト完了")
    except Exception as e:
        logger.error(f"データベース初期化エラー: {str(e)}", exc_info=True)
        import traceback
        logger.error(traceback.format_exc())

    # アプリケーション状態の初期化
    app.state.initialized = True

    # モザイクサービスの初期化を確認
    try:
        if mosaic_service_instance is not None:
            # 設定をロード
            logger.debug("MosaicServiceインスタンス: %s", mosaic_service_instance)
            settings_repo = provide_settings_repository()
            logger.debug("SettingsRepository作成: %s", settings_repo)

            await mosaic_service_instance.load_settings()
            logger.info("MosaicService initialized and settings loaded")
        else:
            logger.warning("MosaicServiceインスタンスがNoneです")
    except Exception as e:
        logger.error(f"MosaicService初期化エラー: {str(e)}", exc_info=True)
        import traceback
        logger.error(traceback.format_exc())

    logger.info(f"初期化完了！ app.state.initialized = {app.state.initialized}")


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
    # イベントリスナー
    listeners=[on_app_startup],
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
    state={"initialized": False}
)


if __name__ == "__main__":
    import uvicorn

    # UvicornでLitestarアプリを起動
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
