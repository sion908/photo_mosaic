"""
アドミンルート - アドミン用のHTTPエンドポイント定義
"""
import traceback

from litestar import Request, Response, get, post
from litestar.response import Redirect, Template

import config
from adapters.database import SettingsRepository
from core.models import MosaicSettings
from core.services import MosaicService
from infrastructure.auth import requires_auth
from infrastructure.logger import get_logger

logger = get_logger("api.admin_routes")


@get("/admin", sync_to_thread=False)
@requires_auth
async def admin_panel(
    request: Request,
    settings_repo: SettingsRepository,
    mosaic_service: MosaicService
) -> Template:
    """アドミンパネルを表示"""
    try:
        logger.info("アドミンパネル表示リクエスト")
        logger.debug("SettingsRepository: %s", settings_repo)
        logger.debug("MosaicService: %s", mosaic_service)

        # 現在の設定を取得
        try:
            logger.debug("設定の取得を試みます")
            current_settings = await settings_repo.get_settings()
            logger.debug("取得した設定: %s", current_settings)
        except Exception as e:
            logger.error("設定取得中にエラーが発生しました: %s", str(e))
            logger.error(traceback.format_exc())
            current_settings = None

        if not current_settings:
            # デフォルト設定を使用
            logger.info("デフォルト設定を作成します")
            current_settings = MosaicSettings.create_default()
            try:
                # 保存
                logger.debug("デフォルト設定を保存します")
                await settings_repo.save_settings(current_settings)
                logger.info("デフォルト設定を作成しました")
            except Exception as e:
                logger.error("デフォルト設定の保存中にエラーが発生しました: %s", str(e))
                logger.error(traceback.format_exc())

        try:
            logger.debug("参加者数を取得します")
            participant_count = await mosaic_service.get_participant_count()
            logger.debug("参加者数: %d", participant_count)
        except Exception as e:
            logger.error("参加者数取得中にエラーが発生しました: %s", str(e))
            logger.error(traceback.format_exc())
            participant_count = 0

        logger.debug("テンプレートをレンダリングします")
        try:
            return Template(
                template_name="admin.html.jinja",
                context={
                    "settings": current_settings,
                    "cell_sizes": [
                        (10, 10), (20, 20), (30, 30), (50, 50), (100, 100)
                    ],
                    "current_participant_count": participant_count
                }
            )
        except Exception as e:
            logger.error("テンプレートレンダリング中にエラーが発生しました: %s", str(e))
            logger.error(traceback.format_exc())
            return Response(f"テンプレートレンダリングエラー: {str(e)}", status_code=500)
    except Exception as e:
        logger.error(f"アドミンパネル表示エラー: {str(e)}", exc_info=True)
        logger.error(traceback.format_exc())
        return Response(f"Error loading admin panel: {str(e)}", status_code=500)


@post("/admin/settings", sync_to_thread=False)
@requires_auth
async def update_settings(
    request: Request,
    settings_repo: SettingsRepository,
    mosaic_service: MosaicService
) -> Redirect:
    """アドミン設定を更新"""
    try:
        logger.info("設定更新リクエスト受信")

        # フォームデータを取得
        form_data = await request.form()

        # グリッドサイズ設定を取得
        grid_width = int(form_data.get("grid_width", "20"))
        grid_height = int(form_data.get("grid_height", "20"))
        
        # グリッドサイズの制限（極端な値を防ぐ）
        grid_width = max(5, min(100, grid_width))
        grid_height = max(5, min(100, grid_height))
        
        # 出力サイズ設定を取得
        output_width = int(form_data.get("output_width", "1000"))
        output_height = int(form_data.get("output_height", "1000"))
        
        # サイズの制限（極端な値を防ぐ）
        output_width = max(100, min(5000, output_width))
        output_height = max(100, min(5000, output_height))

        settings = MosaicSettings(
            id=1,  # 常に同じIDを使用
            grid_size=(grid_width, grid_height),
            logo_path=form_data.get("logo_path", str(config.SCHOOL_LOGO_PATH)),
            title=form_data.get("title", "校章モザイクアート"),
            subtitle=form_data.get("subtitle", "みんなの思い出でつくる、私たちの学校"),
            output_size=(output_width, output_height),
            regenerate_existing=form_data.get("regenerate_existing") == "on"
        )

        # 設定を保存
        await settings_repo.save_settings(settings)
        logger.info(f"設定を更新しました: {settings}")

        # モザイクサービスに設定を反映
        await mosaic_service.update_settings(settings)

        # 再生成フラグがオンの場合はモザイクを再生成
        if settings.regenerate_existing:
            logger.info("モザイク再生成を開始します")
            await mosaic_service.regenerate_mosaic()

        return Redirect("/admin")
    except Exception as e:
        logger.error(f"設定更新エラー: {str(e)}", exc_info=True)
        return Response(f"Error updating settings: {str(e)}", status_code=500)


@get("/admin/reset", sync_to_thread=False)
@requires_auth
async def reset_confirmation(
    request: Request,
) -> Template:
    """リセット確認ページを表示"""
    return Template(template_name="reset_confirm.html.jinja")


@post("/admin/reset", sync_to_thread=False)
@requires_auth
async def reset_mosaic(
    request: Request,
    mosaic_service: MosaicService
) -> Redirect:
    """モザイクをリセット"""
    try:
        logger.warning("モザイクリセットリクエスト受信")
        form_data = await request.form()
        confirm = form_data.get("confirm", "").lower() == "reset"

        if confirm:
            # 完全リセット
            await mosaic_service.reset_all()
            logger.warning("モザイクの完全リセットを実行しました")
            return Redirect("/admin?reset=success")
        else:
            logger.warning("リセット確認が一致しませんでした")
            return Redirect("/admin/reset?error=confirmation")
    except Exception as e:
        logger.error(f"リセットエラー: {str(e)}", exc_info=True)
        return Response(f"Error resetting mosaic: {str(e)}", status_code=500)
