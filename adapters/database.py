"""
データベースアダプター - SQLiteへのインターフェース
"""
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import config
from core.models import Image, MosaicSettings
from infrastructure.logger import get_logger


class DatabaseManager:
    """SQLiteデータベース管理クラス"""

    def __init__(self, db_path: str = str(config.DB_PATH)):
        self.logger = get_logger("adapters.DatabaseManager")
        self.db_path = db_path
        self.logger.info(f"データベース初期化: {db_path}")

    def initialize(self):
        """データベーススキーマの初期化"""
        try:
            self.logger.info("データベーススキーマの初期化開始")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 画像テーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id TEXT PRIMARY KEY,
                filename TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                used INTEGER DEFAULT 0
            )
            ''')

            # 設定テーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                grid_size TEXT,
                logo_path TEXT,
                title TEXT,
                subtitle TEXT,
                output_size TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            conn.commit()
            conn.close()
            self.logger.info("データベース初期化完了")
        except Exception as e:
            self.logger.error(f"データベース初期化エラー: {str(e)}", exc_info=True)
            raise

    def get_connection(self):
        """データベース接続を取得"""
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            self.logger.error(f"データベース接続エラー: {str(e)}", exc_info=True)
            raise


class ImageRepository:
    """画像データのリポジトリ"""

    def __init__(self, db_manager: DatabaseManager):
        self.logger = get_logger("adapters.ImageRepository")
        self.db_manager = db_manager

    async def save(self, image: Image) -> None:
        """画像メタデータを保存"""
        try:
            self.logger.debug(f"画像保存: id={image.id}, filename={image.filename}")
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO images (id, filename, timestamp, used) VALUES (?, ?, ?, ?)",
                (image.id, image.filename, image.timestamp, int(image.used))
            )
            conn.commit()
            conn.close()
            self.logger.debug("画像メタデータ保存完了")
        except Exception as e:
            self.logger.error(f"画像保存エラー: {str(e)}", exc_info=True)
            raise

    async def get_by_id(self, image_id: str) -> Optional[Image]:
        """IDで画像を検索"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, filename, timestamp, used FROM images WHERE id = ?", (image_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                return Image(
                    id=result[0],
                    filename=result[1],
                    timestamp=datetime.fromisoformat(result[2]),
                    used=bool(result[3])
                )
            self.logger.warning(f"画像ID '{image_id}' が見つかりません")
            return None
        except Exception as e:
            self.logger.error(f"画像検索エラー: {str(e)}", exc_info=True)
            raise

    async def get_filename(self, image_id: str) -> Optional[str]:
        """画像IDからファイル名を取得"""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM images WHERE id = ?", (image_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return result[0]
        return None

    async def get_all(self) -> List[Image]:
        """すべての画像を取得"""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, timestamp, used FROM images")
        results = cursor.fetchall()
        conn.close()

        return [
            Image(
                id=row[0],
                filename=row[1],
                timestamp=datetime.fromisoformat(row[2]),
                used=bool(row[3])
            )
            for row in results
        ]

    async def count(self) -> int:
        """画像の総数を取得"""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM images")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    async def mark_as_used(self, image_id: str) -> None:
        """画像を使用済みとしてマーク"""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE images SET used = 1 WHERE id = ?", (image_id,))
        conn.commit()
        conn.close()

    async def delete_all(self) -> None:
        """すべての画像を削除（リセット用）"""
        try:
            self.logger.warning("すべての画像メタデータの削除を開始")
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM images")
            conn.commit()
            conn.close()
            self.logger.warning("すべての画像メタデータを削除しました")
        except Exception as e:
            self.logger.error(f"画像一括削除エラー: {str(e)}", exc_info=True)
            raise


class SettingsRepository:
    """設定データのリポジトリ"""

    def __init__(self, db_manager: DatabaseManager):
        self.logger = get_logger("adapters.SettingsRepository")
        self.db_manager = db_manager
        self.logger.debug("SettingsRepository initialized with db_manager: %s", db_manager)

    async def save_settings(self, settings: MosaicSettings) -> None:
        """設定を保存"""
        try:
            self.logger.info(f"設定保存: グリッドサイズ={settings.grid_size}, ロゴパス={settings.logo_path}, 出力サイズ={settings.output_size}")

            # グリッドサイズと出力サイズをJSON文字列に変換
            grid_size_json = json.dumps(settings.grid_size)
            output_size_json = json.dumps(settings.output_size)
            self.logger.debug("Serialized grid_size: %s", grid_size_json)
            self.logger.debug("Serialized output_size: %s", output_size_json)

            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            self.logger.debug("SQL実行前: INSERT/UPDATE settings テーブル")

            # SQLiteバージョンの互換性を確認
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            self.logger.debug("SQLite version: %s", version)

            # UPSERTパターン
            try:
                cursor.execute('''
                    INSERT INTO settings (id, grid_size, logo_path, title, subtitle, output_size, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        grid_size = excluded.grid_size,
                        logo_path = excluded.logo_path,
                        title = excluded.title,
                        subtitle = excluded.subtitle,
                        output_size = excluded.output_size,
                        timestamp = CURRENT_TIMESTAMP
                ''', (
                    settings.id,
                    grid_size_json,
                    settings.logo_path,
                    settings.title,
                    settings.subtitle,
                    output_size_json
                ))

                conn.commit()
                self.logger.debug("SQL実行成功: 設定が保存されました")
            except Exception as sql_error:
                self.logger.error(f"SQLエラー: {str(sql_error)}")

                # 代替方法を試す（古いSQLite版での互換性対応）
                self.logger.debug("代替方法で設定保存を試みます")
                try:
                    # 既存のレコードを確認
                    cursor.execute("SELECT COUNT(*) FROM settings WHERE id = ?", (settings.id,))
                    exists = cursor.fetchone()[0] > 0

                    if exists:
                        # 更新
                        cursor.execute('''
                            UPDATE settings SET
                                grid_size = ?,
                                logo_path = ?,
                                title = ?,
                                subtitle = ?,
                                output_size = ?,
                                timestamp = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (
                            grid_size_json,
                            settings.logo_path,
                            settings.title,
                            settings.subtitle,
                            output_size_json,
                            settings.id
                        ))
                    else:
                        # 挿入
                        cursor.execute('''
                            INSERT INTO settings (id, grid_size, logo_path, title, subtitle, output_size, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ''', (
                            settings.id,
                            grid_size_json,
                            settings.logo_path,
                            settings.title,
                            settings.subtitle,
                            output_size_json
                        ))

                    conn.commit()
                    self.logger.debug("代替方法でSQL実行成功")
                except Exception as alt_error:
                    self.logger.error(f"代替方法でもSQL実行失敗: {str(alt_error)}")
                    raise

            conn.close()
            self.logger.info("設定保存完了")
        except Exception as e:
            self.logger.error(f"設定保存エラー: {str(e)}", exc_info=True)
            import traceback
            self.logger.error(traceback.format_exc())
            raise

    async def get_settings(self) -> Optional[MosaicSettings]:
        """現在の設定を取得"""
        try:
            self.logger.debug("設定取得開始")
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            # テーブル存在確認
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='settings'
            ''')
            if not cursor.fetchone():
                self.logger.warning("settings テーブルが存在しません")
                conn.close()
                return None

            self.logger.debug("settings テーブルからデータを取得します")
            cursor.execute('''
                SELECT id, grid_size, logo_path, title, subtitle, output_size
                FROM settings
                ORDER BY timestamp DESC LIMIT 1
            ''')
            result = cursor.fetchone()
            conn.close()

            if result:
                self.logger.debug("設定が見つかりました: %s", result)
                try:
                    # グリッドサイズをJSONからタプルに変換
                    grid_size = tuple(json.loads(result[1]))
                    self.logger.debug("Parsed grid_size: %s", grid_size)
                    
                    # output_sizeはNULLの可能性があるので、デフォルト値を設定
                    output_size = config.DEFAULT_OUTPUT_SIZE  # デフォルト値
                    if result[5]:  # output_size カラムが存在し、NULLでなければ
                        try:
                            output_size = tuple(json.loads(result[5]))
                            self.logger.debug("Parsed output_size: %s", output_size)
                        except Exception as json_error:
                            self.logger.warning(f"output_size の解析に失敗しました: {str(json_error)}")
                            self.logger.debug(f"解析に失敗したJSON: {result[5]}")

                    return MosaicSettings(
                        id=result[0],
                        grid_size=grid_size,
                        logo_path=result[2],
                        title=result[3],
                        subtitle=result[4],
                        output_size=output_size,
                        regenerate_existing=False  # DBには保存しないフラグ
                    )
                except json.JSONDecodeError as json_error:
                    self.logger.error(f"JSON解析エラー: {str(json_error)}")
                    self.logger.debug(f"解析に失敗したJSON: {result[1]}")
                    raise

                self.logger.info("設定が見つかりません。デフォルト設定を使用します。")
                return None
        except Exception as e:
            self.logger.error(f"設定取得エラー: {str(e)}", exc_info=True)
            import traceback
            self.logger.error(traceback.format_exc())
            # エラー時はデフォルト設定を返す
            return MosaicSettings.create_default()
