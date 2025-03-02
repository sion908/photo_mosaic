import config
from adapters.database import DatabaseManager

# データベースマネージャーを初期化
db_manager = DatabaseManager()

# テーブルを作成
db_manager.initialize()
print("テーブルを作成しました。")
