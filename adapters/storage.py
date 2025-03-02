"""
ファイルストレージアダプター - ファイルシステムへのインターフェース
"""
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional

import config
from infrastructure.logger import get_logger


class FileStorage:
    """ファイル保存・管理クラス"""

    def __init__(
        self,
        upload_dir: str = str(config.UPLOAD_DIR),
        processed_dir: str = str(config.PROCESSED_DIR)
    ):
        self.logger = get_logger("adapters.FileStorage")
        self.upload_dir = Path(upload_dir)
        self.processed_dir = Path(processed_dir)

        # ディレクトリが存在することを確認
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            self.processed_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"ストレージディレクトリ初期化: upload={upload_dir}, processed={processed_dir}")
        except Exception as e:
            self.logger.error(f"ストレージディレクトリ作成エラー: {str(e)}", exc_info=True)
            raise

    async def save_uploaded_file(self, file_id: str, filename: str, content: bytes) -> str:
        """アップロードされたファイルを保存"""
        try:
            # 保存するファイル名を生成
            safe_filename = f"{file_id}_{filename}"
            file_path = self.upload_dir / safe_filename

            self.logger.info(f"ファイル保存開始: id={file_id}, filename={filename}, サイズ={len(content)} bytes")

            # ファイルを保存
            with open(file_path, "wb") as f:
                f.write(content)

            self.logger.info(f"ファイル保存完了: {file_path}")
            return str(file_path)
        except Exception as e:
            self.logger.error(f"ファイル保存エラー: {str(e)}", exc_info=True)
            raise

    def get_upload_path(self, filename: str) -> str:
        """アップロードディレクトリ内のファイルパスを取得"""
        return str(self.upload_dir / filename)

    def get_processed_path(self, filename: str) -> str:
        """処理済みディレクトリ内のファイルパスを取得"""
        return str(self.processed_dir / filename)

    async def delete_file(self, filename: str) -> bool:
        """ファイルを削除"""
        try:
            self.logger.info(f"ファイル削除開始: {filename}")
            original_path = self.upload_dir / filename
            processed_path = self.processed_dir / filename

            deleted = False
            # 両方のパスを確認して削除
            if original_path.exists():
                original_path.unlink()
                self.logger.debug(f"オリジナルファイル削除: {original_path}")
                deleted = True

            if processed_path.exists():
                processed_path.unlink()
                self.logger.debug(f"処理済みファイル削除: {processed_path}")
                deleted = True

            if not deleted:
                self.logger.warning(f"削除対象ファイルが見つかりません: {filename}")

            return deleted
        except Exception as e:
            self.logger.error(f"ファイル削除エラー {filename}: {str(e)}", exc_info=True)
            return False

    async def clear_all_files(self) -> bool:
        """すべてのファイルを削除（テスト用）"""
        try:
            self.logger.warning("すべてのファイルの削除を開始します")

            # アップロードディレクトリのファイルを削除
            for file in self.upload_dir.glob("*"):
                if file.is_file():
                    file.unlink()
                    self.logger.debug(f"ファイル削除: {file}")

            # 処理済みディレクトリのファイルを削除
            for file in self.processed_dir.glob("*"):
                if file.is_file():
                    file.unlink()
                    self.logger.debug(f"ファイル削除: {file}")

            self.logger.info("すべてのファイルの削除が完了しました")
            return True
        except Exception as e:
            self.logger.error(f"ファイル一括削除エラー: {str(e)}", exc_info=True)
            return False
