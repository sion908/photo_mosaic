"""
APIルート - HTTPエンドポイント定義
"""
import os
from typing import Any, Dict

from litestar import Request, get, post
from litestar.datastructures import UploadFile
from litestar.response import Response, Template

import config
from adapters.database import ImageRepository
from adapters.storage import FileStorage
from core.models import Image
from core.services import MosaicService
from infrastructure.logger import get_logger

logger = get_logger("api.routes")

@get("/")
async def index() -> Template:
    """メインページ (アップロード用インターフェース)"""
    try:
        return Template(template_name="upload.html.jinja", context={})
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Index error: {e}")
        return Response(f"Error loading upload page: {str(e)}")


@get("/display")
async def display() -> Template:
    """表示用ページ (大型スクリーン用)"""
    try:
        # 絶対パスからURLパスへの変換
        if os.path.exists(config.MOSAIC_OUTPUT_PATH):
            # モザイク画像が存在する場合
            # 相対URLパスを使用（静的ファイルルートからの相対パス）- キャッシュバスティングなし
            initial_mosaic = "/static/output/current_mosaic.jpg"
        else:
            # モザイク画像がまだ存在しない場合はロゴを使用
            initial_mosaic = "/static/base/school_logo.png"

        print(f"使用する画像パス (URL): {initial_mosaic}")

        return Template(
            template_name="display.html.jinja",
            context={"initial_mosaic": initial_mosaic}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Display error: {e}")
        return Response(f"Error loading display page: {str(e)}")


@post("/upload")
async def upload_image(
    request: Request,
    mosaic_service: MosaicService,
    image_repo: ImageRepository,
    file_storage: FileStorage
) -> Dict[str, Any]:
    """画像アップロードエンドポイント"""
    try:
        logger.info("画像アップロードリクエスト受信")

        # フォームデータからファイルを取得
        form_data = await request.form()
        uploaded_file = form_data.get("image")

        if not uploaded_file:
            logger.warning("アップロードにファイルが含まれていません")
            return {"error": "No image file provided"}

        # UploadFileオブジェクトにはsize属性がないため、contentを読み込んでからサイズを取得する
        logger.info(f"ファイル受信: {uploaded_file.filename}")

        # 画像メタデータを作成
        image = Image.create(uploaded_file.filename)

        # ファイル内容を読み込み
        try:
            content = await uploaded_file.read()
        except Exception as e:
            logger.warning(f"非同期読み込みエラー: {e}, 同期的な読み込みを試みます")
            # 同期的な読み込みを試す
            content = uploaded_file.read()

        # 読み込み後にファイルサイズをログに記録
        logger.info(f"ファイルサイズ: {len(content)} bytes")

        # ファイルを保存
        file_path = await file_storage.save_uploaded_file(
            image.id, image.filename, content
        )
        logger.debug(f"ファイル保存先: {file_path}")

        # データベースに画像メタデータを保存
        await image_repo.save(image)

        # 画像処理とモザイク更新
        try:
            processed_path, update_result = await mosaic_service.process_uploaded_image(
                file_path, image.id
            )
            logger.info(f"画像処理完了: {processed_path}, セル位置: x={update_result.updated_cell['x']}, y={update_result.updated_cell['y']}")
        except Exception as e:
            logger.error(f"画像処理エラー: {str(e)}", exc_info=True)
            return {"error": f"Image processing failed: {str(e)}"}

        return {
            "success": True,
            "file_id": image.id,
            "updated_cell": update_result.updated_cell
        }

    except Exception as e:
        logger.error(f"アップロード処理エラー: {str(e)}", exc_info=True)
        return {"error": str(e)}


@get("/api/stats")
async def get_stats(image_repo: ImageRepository) -> Dict[str, Any]:
    """統計情報API - 参加者数などの情報を取得"""
    try:
        # 画像の総数（参加者数）を取得
        count = await image_repo.count()
        return {"contributor_count": count}

    except Exception as e:
        print(f"Stats error: {e}")
        return {"contributor_count": 0, "error": str(e)}
