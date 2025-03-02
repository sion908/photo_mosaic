import logging
import os
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = "mosaic_app",
    log_level: int = logging.INFO,
    log_dir: str = "logs",
    console_output: bool = True
) -> logging.Logger:
    """
    アプリケーションロガーの設定

    Args:
        name: ロガーの名前
        log_level: ログレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: ログファイルを保存するディレクトリ
        console_output: コンソールにもログを出力するかどうか

    Returns:
        設定されたロガーインスタンス
    """
    # ロガーを取得
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # すでにハンドラが設定されている場合は追加しない
    if logger.handlers:
        return logger

    # フォーマッタを作成
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
    )

    # ファイルハンドラを設定
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    # 日付を含むログファイル名
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir_path / f"{name}_{today}.log"

    # ファイルハンドラ
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # エラーログ専用ハンドラ (ERROR以上のみ)
    error_log_file = log_dir_path / f"{name}_errors_{today}.log"
    error_file_handler = logging.FileHandler(error_log_file, encoding="utf-8")
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    logger.addHandler(error_file_handler)

    # コンソール出力が必要な場合
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    logger.info(f"ロガーを初期化しました: {name}")
    return logger


# アプリケーション全体で使用するロガー
app_logger = setup_logger()


# 特定のモジュール用のロガーを取得する関数
def get_logger(module_name: str) -> logging.Logger:
    """モジュール固有のロガーを取得する"""
    return logging.getLogger(f"mosaic_app.{module_name}")