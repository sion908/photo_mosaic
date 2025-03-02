"""
サービス層 - コアビジネスロジック
"""
import os
import random
import time
import uuid
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image as PILImage

import config
from adapters.database import ImageRepository, SettingsRepository
from adapters.storage import FileStorage
from core.models import Cell, Image, MosaicGrid, MosaicSettings, MosaicUpdate
from infrastructure.channels import ChannelPublisher
from infrastructure.image_processor import ImageProcessor
from infrastructure.logger import get_logger


class MosaicService:
    """モザイクアート生成サービス"""

    def __init__(
        self,
        image_repo: ImageRepository,
        file_storage: FileStorage,
        channel_publisher: ChannelPublisher,
        settings_repo: Optional[SettingsRepository] = None,
        base_image_path: str = str(config.SCHOOL_LOGO_PATH),
        grid_size: Tuple[int, int] = config.DEFAULT_GRID_SIZE,
        output_size: Tuple[int, int] = config.DEFAULT_OUTPUT_SIZE
    ):
        self.logger = get_logger("services.MosaicService")

        self.image_repo = image_repo
        self.file_storage = file_storage
        self.channel_publisher = channel_publisher
        self.settings_repo = settings_repo

        # 初期設定
        self.base_image_path = base_image_path
        self.grid_size = grid_size  # グリッドサイズ（横セル数, 縦セル数）
        self.output_size = output_size
        self.title = "校章モザイクアート"
        self.subtitle = "みんなの思い出でつくる、私たちの学校"

        # セルサイズは出力サイズとグリッドサイズから計算
        self.cell_size = self._calculate_cell_size()

        self.logger.info(f"MosaicServiceを初期化: グリッドサイズ={grid_size}, ベース画像={base_image_path}, 出力サイズ={output_size}")
        self.grid = self._initialize_grid()

    def _calculate_cell_size(self) -> Tuple[int, int]:
        """出力サイズとグリッドサイズからセルサイズを計算"""
        cell_width = self.output_size[0] // self.grid_size[0]
        cell_height = self.output_size[1] // self.grid_size[1]
        return (cell_width, cell_height)

    async def load_settings(self) -> None:
        """設定をロード"""
        if self.settings_repo:
            try:
                settings = await self.settings_repo.get_settings()
                if settings:
                    self.logger.info(f"設定をロードしました: グリッドサイズ={settings.grid_size}, ロゴパス={settings.logo_path}, 出力サイズ={settings.output_size}")
                    await self.update_settings(settings)
                else:
                    self.logger.info("設定が見つかりませんでした。デフォルト設定を使用します。")
                    # デフォルト値を設定
                    self.grid_size = config.DEFAULT_GRID_SIZE
                    self.output_size = config.DEFAULT_OUTPUT_SIZE
                    self.cell_size = self._calculate_cell_size()
            except Exception as e:
                self.logger.error(f"設定ロードエラー: {str(e)}", exc_info=True)
                # エラーが発生してもサービスは継続
                self.grid_size = config.DEFAULT_GRID_SIZE
                self.output_size = config.DEFAULT_OUTPUT_SIZE
                self.cell_size = self._calculate_cell_size()
        else:
            # 設定リポジトリがない場合はデフォルト値を使用
            self.grid_size = config.DEFAULT_GRID_SIZE
            self.output_size = config.DEFAULT_OUTPUT_SIZE
            self.cell_size = self._calculate_cell_size()

    async def update_settings(self, settings: MosaicSettings) -> bool:
        """設定を更新"""
        try:
            self.logger.info(f"設定更新: グリッドサイズ={settings.grid_size}, ロゴパス={settings.logo_path}, 出力サイズ={settings.output_size}")

            # 設定を保存
            if self.settings_repo:
                await self.settings_repo.save_settings(settings)

            # 設定を反映
            old_grid_size = self.grid_size
            old_base_image = self.base_image_path
            old_output_size = self.output_size

            self.grid_size = settings.grid_size
            self.base_image_path = settings.logo_path
            self.output_size = settings.output_size
            self.title = settings.title
            self.subtitle = settings.subtitle
            
            # セルサイズを再計算
            self.cell_size = self._calculate_cell_size()
            self.logger.info(f"新しいセルサイズ: {self.cell_size} (自動計算)")

            # グリッドの再初期化が必要かを判断
            need_grid_reinit = (old_grid_size != self.grid_size or 
                                old_base_image != self.base_image_path or
                                old_output_size != self.output_size)

            if need_grid_reinit:
                self.logger.info("グリッドを再初期化します")
                self.grid = self._initialize_grid()

            return need_grid_reinit
        except Exception as e:
            self.logger.error(f"設定更新エラー: {str(e)}", exc_info=True)
            return False

    def _initialize_grid(self) -> MosaicGrid:
        """グリッドを生成"""
        try:
            self.logger.info(f"グリッド初期化開始: グリッドサイズ={self.grid_size}")

            # ベース画像をロード（明るさの分析用）
            base_image = PILImage.open(self.base_image_path)
            
            # ベース画像をグリッドサイズに合わせてリサイズ
            analysis_size = (self.grid_size[0], self.grid_size[1])
            
            # 小さくリサイズして明るさ分析用に使用
            base_resized = base_image.resize(analysis_size)
            base_gray = base_resized.convert("L")
            
            # グリッドセルを作成
            cells = []
            grid_width, grid_height = self.grid_size
            
            # 各セルの明るさを分析
            for y in range(grid_height):
                for x in range(grid_width):
                    # 対応するピクセルの明るさを取得
                    brightness = base_gray.getpixel((x, y))
                    
                    # コントラスト計算のための周辺ピクセル取得（範囲外アクセス防止）
                    neighbors = []
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < grid_width and 0 <= ny < grid_height:
                                neighbors.append(base_gray.getpixel((nx, ny)))
                    
                    # 周辺ピクセルとの差の標準偏差でコントラストを計算
                    if len(neighbors) > 1:
                        contrast = np.std(neighbors)
                    else:
                        contrast = 0
                        
                    cells.append(Cell(
                        x=x,
                        y=y,
                        brightness=float(brightness),
                        contrast=float(contrast),
                        last_updated=0.0
                    ))

            self.logger.info(f"グリッド初期化完了: {len(cells)}セル作成")

            return MosaicGrid(
                width=grid_width,
                height=grid_height,
                cells=cells,
                cell_size=self.cell_size
            )
        except FileNotFoundError:
            self.logger.error(f"ベース画像が見つかりません: {self.base_image_path}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"グリッド初期化エラー: {str(e)}", exc_info=True)
            raise

    async def add_image(self, image_path: str, image_id: str) -> MosaicUpdate:
        """新しい画像を追加してモザイクを更新"""
        try:
            self.logger.info(f"画像追加開始: {image_path}, id={image_id}")
            img = PILImage.open(image_path)

            # 画像の色調解析をより詳細に
            img_gray = img.convert("L")
            img_array = np.array(img_gray)
            img_brightness = img_array.mean()
            img_contrast = img_array.std()  # コントラストも考慮

            self.logger.debug(f"画像特性: 明るさ={img_brightness:.2f}, コントラスト={img_contrast:.2f}")

            # より適切なセル選択アルゴリズム
            empty_cells = [cell for cell in self.grid.cells if cell.image_id is None]

            if not empty_cells:
                # すべてのセルが埋まっている場合、最も古い画像を置き換え
                self.logger.info("空のセルがありません。最も古いセルを置き換えます。")
                cell_to_update = min(self.grid.cells, key=lambda c: c.last_updated)
                self.logger.debug(f"置き換えるセル: x={cell_to_update.x}, y={cell_to_update.y}, 最終更新={cell_to_update.last_updated}")
            else:
                # 明るさの差とコントラストを加味した重み付けスコア
                self.logger.debug(f"空のセル数: {len(empty_cells)}")

                # 明るさとコントラストの類似度でスコア計算
                def calculate_score(cell):
                    brightness_diff = abs(cell.brightness - img_brightness)
                    contrast_diff = abs(cell.contrast - img_contrast)
                    # 0.7と0.3の重みで明るさとコントラストを考慮
                    return brightness_diff * 0.7 + contrast_diff * 0.3

                cell_to_update = min(empty_cells, key=calculate_score)
                self.logger.debug(f"選択したセル: x={cell_to_update.x}, y={cell_to_update.y}, 明るさ={cell_to_update.brightness:.2f}, コントラスト={cell_to_update.contrast:.2f}")

            # セルを更新
            cell_to_update.image_id = image_id
            cell_to_update.last_updated = time.time()  # 置き換え時間を記録

            self.logger.info(f"セル更新: x={cell_to_update.x}, y={cell_to_update.y}, id={image_id}")

            # モザイク全体を再構築して保存
            await self.render_mosaic()

            return MosaicUpdate(
                updated_cell={"x": cell_to_update.x, "y": cell_to_update.y},
                file_id=image_id
            )
        except Exception as e:
            self.logger.error(f"画像追加エラー: {str(e)}", exc_info=True)
            raise

    async def render_mosaic(self) -> str:
        """現在のグリッド情報を使ってモザイク画像を生成"""
        try:
            self.logger.info("モザイク画像生成開始")

            # 出力ディレクトリを確保
            output_dir = os.path.dirname(config.MOSAIC_OUTPUT_PATH)
            os.makedirs(output_dir, exist_ok=True)

            # 最終出力サイズとセルサイズを取得
            final_width, final_height = self.output_size
            cell_width, cell_height = self.cell_size
            
            # グリッドサイズの確認
            grid_width, grid_height = self.grid.width, self.grid.height
            
            self.logger.debug(f"モザイク生成パラメータ: 出力サイズ={self.output_size}, セルサイズ={self.cell_size}, グリッド={grid_width}x{grid_height}")
            
            # 計算されるキャンバスサイズ
            canvas_width = grid_width * cell_width
            canvas_height = grid_height * cell_height
            
            # もし計算されたサイズが出力サイズと異なる場合は調整（通常はわずかな差）
            if canvas_width != final_width or canvas_height != final_height:
                self.logger.warning(f"キャンバスサイズ調整: {canvas_width}x{canvas_height} -> {final_width}x{final_height}")
                # セルサイズを微調整（小数点以下の差を考慮）
                cell_width = final_width / grid_width
                cell_height = final_height / grid_height

            # 新しいキャンバスを作成（出力サイズで直接作成）
            mosaic = PILImage.new("RGB", (final_width, final_height))

            images_placed = 0
            errors = 0

            # 各セルに画像を配置
            for cell in self.grid.cells:
                # セルの位置を計算（小数点以下の位置にも対応）
                x1 = int(cell.x * cell_width)
                y1 = int(cell.y * cell_height)
                x2 = int((cell.x + 1) * cell_width)
                y2 = int((cell.y + 1) * cell_height)
                
                # 実際のセルサイズ（小数点以下の位置調整後）
                actual_cell_width = x2 - x1
                actual_cell_height = y2 - y1

                if cell.image_id:
                    # セルに画像がある場合はそれを取得して配置
                    try:
                        image_filename = await self.image_repo.get_filename(cell.image_id)
                        if not image_filename:
                            self.logger.warning(f"画像ID {cell.image_id} のファイル名が見つかりません")
                            continue

                        img_path = self.file_storage.get_processed_path(f"{cell.image_id}_{image_filename}")
                        try:
                            cell_img = PILImage.open(img_path)
                            # セルのサイズにリサイズ
                            cell_img = cell_img.resize((actual_cell_width, actual_cell_height))
                            mosaic.paste(cell_img, (x1, y1))
                            images_placed += 1
                        except Exception as e:
                            self.logger.error(f"画像配置エラー {img_path}: {str(e)}")
                            errors += 1
                    except Exception as e:
                        self.logger.error(f"セル処理エラー x={cell.x}, y={cell.y}: {str(e)}")
                        errors += 1
                else:
                    # 画像がない場合は明るさに応じたグレーで埋める
                    brightness = int(cell.brightness)
                    cell_img = PILImage.new("RGB", (actual_cell_width, actual_cell_height), (brightness, brightness, brightness))
                    mosaic.paste(cell_img, (x1, y1))

            # 保存
            output_path = str(config.MOSAIC_OUTPUT_PATH)
            mosaic.save(output_path, quality=95)  # JPEG品質を最高に設定
            self.logger.info(f"モザイク画像を保存: {output_path} (配置画像: {images_placed}, エラー: {errors}, サイズ: {final_width}x{final_height})")

            # WebSocket経由で更新通知 (URLパスを生成)
            url_path = "/static/output/current_mosaic.jpg"
            self.channel_publisher.publish_update(url_path)

            # デバッグ出力
            self.logger.debug(f"モザイク画像の最終サイズ: {final_width}x{final_height}")
            self.logger.debug(f"セルサイズ: {self.cell_size}")
            self.logger.debug(f"グリッドのサイズ: {self.grid.width}x{self.grid.height}")
            self.logger.debug(f"セルの数: {len(self.grid.cells)}")
            self.logger.debug(f"画像がセットされたセルの数: {sum(1 for cell in self.grid.cells if cell.image_id is not None)}")

            return url_path
        except Exception as e:
            self.logger.error(f"モザイク生成エラー: {str(e)}", exc_info=True)
            raise

    async def process_uploaded_image(self, original_path: str, image_id: str) -> Tuple[str, MosaicUpdate]:
        """アップロードされた画像を処理してモザイクに追加"""
        # 画像処理
        processed_path = await ImageProcessor.process_image(
            original_path, self.cell_size
        )

        # モザイク更新
        update_result = await self.add_image(processed_path, image_id)

        return processed_path, update_result

    async def get_participant_count(self) -> int:
        """参加者数（画像総数）を取得"""
        return await self.image_repo.count()

    async def regenerate_mosaic(self) -> bool:
        """既存の画像でモザイクを再生成"""
        try:
            self.logger.info("モザイク再生成開始")

            # グリッドを再初期化
            self.grid = self._initialize_grid()

            # すべての画像を取得
            images = await self.image_repo.get_all()
            self.logger.info(f"再生成対象画像数: {len(images)}")

            # 各画像を処理して追加
            for image in images:
                try:
                    # 処理済み画像のパスを取得
                    processed_path = self.file_storage.get_processed_path(f"{image.id}_{image.filename}")

                    # 画像処理が必要な場合（セルサイズが変わった場合など）
                    original_path = self.file_storage.get_upload_path(f"{image.id}_{image.filename}")
                    if os.path.exists(original_path):
                        # オリジナル画像が存在する場合、セルサイズに合わせて再処理
                        processed_path = await ImageProcessor.process_image(
                            original_path, self.cell_size
                        )

                    # モザイクに追加
                    if os.path.exists(processed_path):
                        await self.add_image(processed_path, image.id)
                    else:
                        self.logger.warning(f"処理済み画像が見つかりません: {processed_path}")
                except Exception as e:
                    self.logger.error(f"画像 {image.id} の再生成エラー: {str(e)}")
                    # 個別のエラーで全体の処理は停止しない

            # 最終的なモザイクを保存・通知
            await self.render_mosaic()

            self.logger.info("モザイク再生成完了")
            return True
        except Exception as e:
            self.logger.error(f"モザイク再生成エラー: {str(e)}", exc_info=True)
            return False

    async def reset_all(self) -> bool:
        """すべてのデータをリセット"""
        try:
            self.logger.warning("システム全体リセット開始")

            # 1. データベースからすべての画像メタデータを削除
            await self.image_repo.delete_all()

            # 2. ファイルシステムから画像ファイルを削除
            await self.file_storage.clear_all_files()

            # 3. モザイク画像を削除
            if os.path.exists(config.MOSAIC_OUTPUT_PATH):
                os.remove(config.MOSAIC_OUTPUT_PATH)
                self.logger.info(f"モザイク画像を削除: {config.MOSAIC_OUTPUT_PATH}")

            # 4. グリッドを再初期化
            self.grid = self._initialize_grid()

            # 5. 空のモザイク画像を生成
            await self.render_mosaic()

            self.logger.warning("システム全体リセット完了")
            return True
        except Exception as e:
            self.logger.error(f"リセットエラー: {str(e)}", exc_info=True)
            return False
