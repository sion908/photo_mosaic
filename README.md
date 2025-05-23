# キャンドルモザイクアート生成アプリケーション

## 概要

このアプリケーションは、閉校イベントでのキャンドルナイトにおいて、参加者が制作したキャンドルの写真を収集し、校章をベースとしたモザイクアートをリアルタイムで生成・表示するためのWebアプリケーションです。参加者がアップロードした写真が校章のモザイクアートの一部として組み込まれ、大型スクリーンにリアルタイムで表示されます。

## 主な機能

- **写真アップロード**: 参加者がキャンドルの写真を簡単にアップロード
- **リアルタイム更新**: WebSocketを使用した大型スクリーン向けリアルタイム表示
- **インテリジェントな画像配置**: 写真の明るさや対比度に応じた最適な配置
- **参加者カウント**: 参加者数のリアルタイム表示
- **管理パネル**: 管理者用設定画面によるカスタマイズ

## システム要件

- Python 3.8以上
- 必要なパッケージ:
  - Litestar (ASGIフレームワーク)
  - Pillow (PIL)
  - NumPy
  - Jinja2
  - Uvicorn

## インストール方法

### 通常のインストール

```bash
# リポジトリのクローン
git clone <リポジトリURL>
cd photo_mosaic

# 仮想環境の作成（推奨）
python -m venv venv
source venv/bin/activate  # Linuxの場合
venv\Scripts\activate     # Windowsの場合

# 依存パッケージのインストール
pip install -r requirements.txt
```

### Poetry を使用したインストール

```bash
# リポジトリのクローン
git clone <リポジトリURL>
cd photo_mosaic

# Poetry を使用してパッケージをインストール
poetry install
```

### Docker を使用したインストール

```bash
# リポジトリのクローン
git clone <リポジトリURL>
cd photo_mosaic

# Dockerイメージのビルドと起動
docker-compose up -d
```

## 使い方

### サーバーの起動

```bash
# 開発サーバー起動
python app.py
```

または Poetry を使用している場合:

```bash
poetry run python app.py
```

サーバーは以下のURLでアクセスできます:
- アップロード用インターフェース: `http://localhost:8000/`
- 表示用画面（大型スクリーン向け）: `http://localhost:8000/display`
- 管理パネル: `http://localhost:8000/admin` (Basic認証が必要)

### 管理パネルへのアクセス

管理パネルには初期設定として以下の認証情報でアクセスできます:
- ユーザー名: `admin`
- パスワード: `candle2025`

セキュリティ上の理由から、本番環境では環境変数を使用して認証情報を変更することを強く推奨します:

```bash
export ADMIN_USERNAME=新しいユーザー名
export ADMIN_PASSWORD=新しいパスワード
```

## プロジェクト構造

このプロジェクトはオニオンアーキテクチャに基づいて設計されています:

```
photo_mosaic/
│
├── app.py                # アプリケーションのエントリーポイント
├── config.py             # 設定ファイル
│
├── core/                 # コアドメインロジック
│   ├── models.py         # ドメインモデル
│   └── services.py       # ビジネスロジックサービス
│
├── adapters/             # 二次的なもの（DB、外部API等）のアダプタ
│   ├── database.py       # データベースアダプター
│   └── storage.py        # ファイル保存アダプター
│
├── infrastructure/       # インフラストラクチャ層
│   ├── channels.py       # WebSocketチャンネル関連
│   ├── image_processor.py # 画像処理インフラ
│   └── auth.py           # 認証関連
│
├── interfaces/           # 外部インターフェース
│   ├── api/              # APIエンドポイント
│   │   ├── routes.py     # HTTPルート定義
│   │   └── websockets.py # WebSocketハンドラ
│   └── web/              # Webインターフェース
│       └── templates/    # Jinja2テンプレート
│
└── static/               # 静的ファイル
    ├── base/             # 基本画像（校章など）
    └── output/           # 生成されたモザイク画像
```

## カスタマイズ方法

### 校章画像の変更

1. `static/base/` ディレクトリに新しい校章画像を配置します
2. 管理パネルにアクセスし、「校章画像パス」設定を変更します

### モザイクグリッドサイズの設定

1. 管理パネルにアクセスします
2. 「グリッドサイズ」の値を変更します（例: 20×20、30×30など）
3. イベント規模に合わせて適切な値を設定してください

### 出力画像サイズの設定

1. 管理パネルにアクセスします
2. 「出力サイズ」の値を変更します（例: 1000×1000、2000×2000など）
3. 表示用スクリーンの解像度に合わせて設定してください

## 高度な設定

`config.py` ファイルでは以下の設定を変更できます:

- `UPLOAD_DIR`: アップロードされたファイルの保存先
- `PROCESSED_DIR`: 処理済みファイルの保存先
- `SELF_UPLOAD_DIR`: セルフアップロード用ディレクトリ
- `LOG_LEVEL`: ログのレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- `WS_CHANNEL_NAME`: WebSocketチャンネル名
- `WS_HISTORY_SIZE`: WebSocket履歴サイズ

## 運用のヒント

- 閉校イベント当日は、`self_uploads` ディレクトリをネットワーク共有として設定すると、管理者が一括で写真をアップロードできます
- 安定した運用のためにUPSなどの無停電電源装置を使用することをお勧めします
- 大型スクリーン用の画面は全画面表示モードで表示してください

## トラブルシューティング

**問題**: 写真をアップロードしてもモザイクが更新されない
**解決策**: 
- ログファイル（`logs/`ディレクトリ）を確認する
- 「モザイクをリセット」機能を試す
- サーバーを再起動する

**問題**: WebSocket接続エラー
**解決策**:
- ブラウザのコンソールでエラーを確認する
- ファイアウォール設定を確認する
- サーバーを再起動する

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

バグ報告や機能追加のリクエストは、GitHubのIssueトラッカーへお願いします。
