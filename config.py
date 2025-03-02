"""
アプリケーション設定モジュール
"""
import logging
import os
from pathlib import Path

# プロジェクトのベースディレクトリ
BASE_DIR = Path(__file__).parent

# データ保存関連
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = UPLOAD_DIR / "processed"
SELF_UPLOAD_DIR = BASE_DIR / "self_uploads"
DB_PATH = BASE_DIR / "mosaic_app.db"

# 画像関連
MOSAIC_OUTPUT_PATH = BASE_DIR / "static" / "output" / "current_mosaic.jpg"
SCHOOL_LOGO_PATH = BASE_DIR / "static" / "base" / "school_logo.png"

# 画像処理設定
CELL_SIZE = (50, 50)
DEFAULT_GRID_SIZE = (20, 20)
DEFAULT_OUTPUT_SIZE = (1000, 1000)

# テンプレート設定
TEMPLATE_DIR = BASE_DIR / "interfaces" / "web" / "templates"

# 静的ファイル設定
STATIC_DIR = BASE_DIR / "static"

# WebSocketチャンネル設定
WS_CHANNEL_NAME = "mosaic"
WS_HISTORY_SIZE = 10
WS_SEND_HISTORY = 5

# 管理者認証設定
ADMIN_USERNAME = "admin"  # デフォルト値（環境変数でオーバーライド推奨）
ADMIN_PASSWORD = "candle2025"  # デフォルト値（環境変数でオーバーライド推奨）

# ロギング設定
LOG_DIR = BASE_DIR / "logs"
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# ロギングレベルの辞書（文字列からロギングレベルへの変換用）
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# 環境変数からログレベルを設定できるようにする
def get_log_level() -> int:
    """環境変数からログレベルを取得"""
    level_name = os.environ.get("LOG_LEVEL", LOG_LEVEL)
    return LOG_LEVELS.get(level_name, logging.INFO)

# ディレクトリ初期化
def ensure_directories():
    """必要なディレクトリが存在することを確認"""
    for directory in [
        UPLOAD_DIR,
        PROCESSED_DIR,
        SELF_UPLOAD_DIR,
        MOSAIC_OUTPUT_PATH.parent,
        SCHOOL_LOGO_PATH.parent,
        LOG_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)