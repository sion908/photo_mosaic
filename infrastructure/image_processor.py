"""
画像処理モジュール - 写真を正方形にトリミングする処理
"""
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageEnhance, ImageOps

import config
from infrastructure.logger import get_logger

logger = get_logger("infrastructure.ImageProcessor")


class ImageProcessor:
    """画像処理ユーティリティクラス"""

    @staticmethod
    async def process_image(file_path: str, target_size: Tuple[int, int] = (100, 100)) -> str:
        """
        アップロードされた画像を処理して正方形にトリミング

        Args:
            file_path: 処理する画像ファイルのパス
            target_size: 参考用のサイズ (実際にはアスペクト比1:1の正方形にトリミングのみ)

        Returns:
            処理済み画像のファイルパス
        """
        try:
            logger.info(f"画像処理開始: {file_path}")

            # 画像をロード
            img = Image.open(file_path)
            original_size = img.size
            logger.debug(f"元画像サイズ: {original_size}")

            # 正方形にトリミング（中央部分を使用）
            img = ImageOps.fit(img, (min(original_size), min(original_size)), centering=(0.5, 0.5))
            logger.debug(f"トリミング完了: 正方形 {img.size}")

            # 出力パスを設定
            input_path = Path(file_path)
            processed_dir = config.PROCESSED_DIR
            processed_dir.mkdir(exist_ok=True, parents=True)

            output_filename = input_path.name
            output_path = processed_dir / output_filename

            # 画像を保存
            img.save(output_path)
            logger.info(f"処理済み画像を保存: {output_path}")

            return str(output_path)
        except Exception as e:
            logger.error(f"画像処理エラー: {str(e)}", exc_info=True)
            raise

    @staticmethod
    async def enhance_image(file_path: str, contrast: float = 1.2, sharpness: float = 1.1) -> str:
        """
        画像の品質を向上させる（コントラスト調整、シャープネス強化）

        Args:
            file_path: 処理する画像ファイルのパス
            contrast: コントラスト倍率 (1.0が元の画像)
            sharpness: シャープネス倍率 (1.0が元の画像)

        Returns:
            処理済み画像のファイルパス
        """
        try:
            logger.info(f"画像品質向上処理開始: {file_path}, コントラスト: {contrast}, シャープネス: {sharpness}")

            # 画像をロード
            img = Image.open(file_path)

            # コントラスト調整
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(contrast)
            logger.debug(f"コントラスト調整完了: {contrast}倍")

            # シャープネス強化
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(sharpness)
            logger.debug(f"シャープネス強化完了: {sharpness}倍")

            # 出力パスを設定
            output_path = f"{file_path.rsplit('.', 1)[0]}_enhanced.{file_path.rsplit('.', 1)[1]}"

            # 画像を保存
            img.save(output_path)
            logger.info(f"品質向上済み画像を保存: {output_path}")

            return output_path
        except Exception as e:
            logger.error(f"画像品質向上処理エラー: {str(e)}", exc_info=True)
            raise
