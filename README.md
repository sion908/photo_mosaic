# 校章モザイクアート生成アプリケーション

閉校イベントでのキャンドルナイトにおいて、参加者が制作したキャンドルの写真を収集し、校章をベースとしたモザイクアートをリアルタイムで生成・表示するWebアプリケーションです。

## 機能

- 参加者がキャンドルの写真をアップロード
- 写真から校章のモザイクアートをリアルタイムに生成
- WebSocketを使った大スクリーン向けリアルタイム表示
- 写真の明るさに応じた最適な配置
- 参加者数のリアルタイムカウント表示

## アーキテクチャ

このプロジェクトはオニオンアーキテクチャに基づいて設計されています:

1. **コア層**: ドメインモデルとビジネスロジック
2. **アダプター層**: データベースやファイルストレージなどの二次的な関心事
3. **インフラストラクチャ層**: 技術的な実装（画像処理、WebSocket通信など）
4. **インターフェース層**: 外部とのインターフェース（API、WebSocket、テンプレート）

## 環境構築

### 前提条件

- Python 3.8以上
- pipまたはpoetry

### インストール

```bash
# リポジトリのクローン
git clone <レポジトリURL>
cd photo_mosaic

# 仮想環境の作成（オプション）
python -m venv venv
source venv/bin/activate  # Linuxの場合
venv\Scripts\activate     # Windowsの場合

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 設定

1. 静的フォルダに校章画像を配置:
   - `static/base/school_logo.png`

2. 必要なディレクトリは自動的に作成されます

## 実行方法

```bash
# 開発サーバー起動
python app.py
```

以下のURLでアクセスできます:
- アップロード用インターフェース: http://localhost:8000/
- 表示用画面（大型スクリーン向け）: http://localhost:8000/display

## プロジェクト構造

```
photo_mosaic/
│
├── app.py                # アプリケーションのエントリーポイント
├── config.py             # 設定ファイル
│
├── core/                 # コアドメインロジック
│   ├── __init__.py
│   ├── models.py         # ドメインモデル
│   └── services.py       # ビジネスロジックサービス
│
├── adapters/             # 二次的なもの（DB、外部API等）のアダプタ
│   ├── __init__.py
│   ├── database.py       # データベースアダプター
│   └── storage.py        # ファイル保存アダプター
│
├── infrastructure/       # インフラストラクチャ層
│   ├── __init__.py
│   ├── channels.py       # WebSocketチャンネル関連
│   └── image_processor.py # 画像処理インフラ
│
├── interfaces/           # 外部インターフェース
│   ├── __init__.py
│   ├── api/              # APIエンドポイント
│   │   ├── __init__.py
│   │   ├── routes.py     # HTTPルート定義
│   │   └── websockets.py # WebSocketハンドラ
│   └── web/              # Webインターフェース
│       ├── __init__.py
│       └── templates/    # Jinja2テンプレート
│           ├── display.html.jinja
│           └── upload.html.jinja
│
└── static/               # 静的ファイル
    ├── base/             # 基本画像（校章など）
    └── output/           # 生成されたモザイク画像
```

## 技術スタック

- **Webフレームワーク**: Litestar (ASGIフレームワーク)
- **テンプレートエンジン**: Jinja2
- **データベース**: SQLite
- **画像処理**: Pillow (PIL)
- **WebSocket**: Litestar Channels
- **サーバー**: Uvicorn

## 拡張性

- Redis/Postgresバックエンドに切り替えてスケーリング可能
- 画像処理アルゴリズムのカスタマイズ容易
- モザイクデザインの変更可能

## ライセンス

MITライセンス
