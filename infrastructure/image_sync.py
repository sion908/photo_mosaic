"""
画像同期サービス - アプリケーション起動時の画像整合性確保
"""
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Set, Tuple

import config
from adapters.database import ImageRepository
from core.models import Image
from infrastructure.image_processor import ImageProcessor
from infrastructure.logger import get_logger

logger = get_logger("infrastructure.ImageSyncService")

# self_uploadsフォルダのパス
SELF_UPLOAD_DIR = Path(config.BASE_DIR) / "self_uploads"


class ImageSyncService:
    """アプリケーション起動時に画像の整合性を確保するサービス"""

    def __init__(self, image_repo: ImageRepository):
        self.image_repo = image_repo
        self.upload_dir = Path(config.UPLOAD_DIR)
        self.processed_dir = Path(config.PROCESSED_DIR)
        self.logger = logger

    async def sync_images(self) -> Tuple[int, int, int, int]:
        """
        画像の同期を実行

        Returns:
            Tuple[int, int, int, int]: (処理された画像数, 新規追加画像数, self_uploads処理数, エラー数)
        """
        self.logger.info("画像同期処理を開始")

        # self_uploadsフォルダからファイルを移動
        self_upload_count = await self._process_self_uploads()
        self.logger.info(f"self_uploads処理数: {self_upload_count}")

        # データベースから全画像メタデータを取得
        db_images = await self.image_repo.get_all()
        self.logger.info(f"データベースから取得した画像数: {len(db_images)}")

        # ファイルシステムから全画像を取得
        upload_files = self._get_upload_files()
        self.logger.info(f"アップロードディレクトリの画像数: {len(upload_files)}")
        
        processed_files = self._get_processed_files()
        self.logger.info(f"処理済みディレクトリの画像数: {len(processed_files)}")

        # 処理済みファイルをベースにデータベース整合性を確保
        added_count = await self._sync_db_with_processed_files(processed_files, db_images)
        
        # アップロードフォルダから未処理の画像を処理
        processed_count, error_count = await self._process_new_uploads(upload_files, processed_files)

        self.logger.info(f"画像同期完了: 処理={processed_count}, 追加={added_count}, self_uploads={self_upload_count}, エラー={error_count}")
        return processed_count, added_count, self_upload_count, error_count
        
    async def _process_self_uploads(self) -> int:
        """
        self_uploadsフォルダからファイルを処理してuploadsフォルダに移動する

        Returns:
            int: 処理されたファイル数
        """
        self.logger.info("self_uploadsフォルダの処理を開始")
        
        # フォルダが存在しない場合は作成
        SELF_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        processed_count = 0
        
        try:
            # self_uploadsフォルダのファイルを取得
            for file_path in SELF_UPLOAD_DIR.glob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    try:
                        # 新しいUUIDを生成
                        image_id = uuid.uuid4().hex
                        
                        # 元のファイル名を保持
                        original_filename = file_path.name
                        
                        # 新しいファイル名を作成: <UUID>_<元のファイル名>
                        new_filename = f"{image_id}_{original_filename}"
                        
                        # 移動先のパス
                        dest_path = self.upload_dir / new_filename
                        
                        # ファイルをコピー
                        shutil.copy2(file_path, dest_path)
                        self.logger.info(f"ファイルをコピーしました: {file_path} -> {dest_path}")
                        
                        # 元のファイルを削除
                        file_path.unlink()
                        self.logger.info(f"元のファイルを削除しました: {file_path}")
                        
                        processed_count += 1
                        
                    except Exception as e:
                        self.logger.error(f"ファイル {file_path} の処理エラー: {str(e)}", exc_info=True)
            
            self.logger.info(f"self_uploadsフォルダの処理完了: {processed_count}個のファイルを処理")
            
        except Exception as e:
            self.logger.error(f"self_uploadsフォルダの処理中にエラーが発生: {str(e)}", exc_info=True)
        
        return processed_count

    def _get_upload_files(self) -> Set[str]:
        """アップロードディレクトリ内のファイル名を取得"""
        upload_files = set()
        try:
            for file in self.upload_dir.glob("*"):
                if file.is_file() and not file.name.startswith("."):
                    upload_files.add(file.name)
        except Exception as e:
            self.logger.error(f"アップロードディレクトリの読み取りエラー: {str(e)}", exc_info=True)
        return upload_files

    def _get_processed_files(self) -> Set[str]:
        """処理済みディレクトリ内のファイル名を取得"""
        processed_files = set()
        try:
            for file in self.processed_dir.glob("*"):
                if file.is_file() and not file.name.startswith("."):
                    processed_files.add(file.name)
        except Exception as e:
            self.logger.error(f"処理済みディレクトリの読み取りエラー: {str(e)}", exc_info=True)
        return processed_files

    async def _sync_db_with_processed_files(self, processed_files: Set[str], db_images: List[Image]) -> int:
        """
        処理済みファイルを基にデータベースを同期する

        Args:
            processed_files: 処理済みファイル名のセット
            db_images: データベースの画像情報リスト

        Returns:
            int: 新たに追加されたレコード数
        """
        self.logger.info("データベースと処理済みファイルの同期を開始")
        
        # データベースのファイル名集合
        db_filenames = {f"{img.id}_{img.filename}" for img in db_images}
        
        # 新たに追加する必要のあるファイル
        added_count = 0
        
        for filename in processed_files:
            if filename not in db_filenames:
                try:
                    # ファイル名からIDと元のファイル名を抽出
                    # 形式: <id>_<filename>
                    parts = filename.split("_", 1)
                    if len(parts) >= 2:
                        image_id = parts[0]
                        original_filename = parts[1]
                        
                        # データベースに追加
                        image = Image(
                            id=image_id,
                            filename=original_filename,
                            timestamp=datetime.now(),
                            used=True  # すでに処理済みなので使用済みとマーク
                        )
                        await self.image_repo.save(image)
                        added_count += 1
                        self.logger.info(f"データベースに追加: {filename}")
                    else:
                        # 不正なファイル名はスキップ
                        self.logger.warning(f"不正なファイル名形式: {filename}")
                except Exception as e:
                    self.logger.error(f"ファイル {filename} のDB同期エラー: {str(e)}", exc_info=True)
        
        self.logger.info(f"データベース同期完了: {added_count}件の画像を追加")
        return added_count

    async def _process_new_uploads(self, upload_files: Set[str], processed_files: Set[str]) -> Tuple[int, int]:
        """
        アップロードされた未処理の画像を処理する

        Args:
            upload_files: アップロードファイル名のセット
            processed_files: 処理済みファイル名のセット

        Returns:
            Tuple[int, int]: (処理された画像数, エラー数)
        """
        self.logger.info("未処理の画像を処理")
        
        processed_count = 0
        error_count = 0
        
        for filename in upload_files:
            # 対応する処理済みファイルがまだない場合
            if filename not in processed_files:
                try:
                    upload_path = self.upload_dir / filename
                    
                    # 画像処理を実行
                    cell_size = config.CELL_SIZE
                    processed_path = await ImageProcessor.process_image(str(upload_path), cell_size)
                    
                    self.logger.info(f"画像処理完了: {filename} -> {processed_path}")
                    processed_count += 1
                    
                    # データベースにメタデータを追加
                    # まずIDとオリジナルファイル名を抽出
                    parts = filename.split("_", 1)
                    if len(parts) >= 2:
                        image_id = parts[0]
                        original_filename = parts[1]
                    else:
                        # 形式が不正な場合は新しいIDを生成
                        image_id = uuid.uuid4().hex
                        original_filename = filename
                    
                    # すでにデータベースに存在するか確認
                    existing_image = await self.image_repo.get_by_id(image_id)
                    if not existing_image:
                        # 新規追加
                        image = Image(
                            id=image_id,
                            filename=original_filename,
                            timestamp=datetime.now(),
                            used=False  # まだモザイクに使用されていない
                        )
                        await self.image_repo.save(image)
                        self.logger.info(f"新規画像メタデータを保存: {image_id}_{original_filename}")
                    
                except Exception as e:
                    self.logger.error(f"画像 {filename} の処理エラー: {str(e)}", exc_info=True)
                    error_count += 1
        
        self.logger.info(f"画像処理完了: {processed_count}件処理, {error_count}件エラー")
        return processed_count, error_count
