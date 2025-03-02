"""
ドメインモデル - アプリケーションの中心的なビジネスオブジェクト
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Cell:
    """モザイクのグリッドセル"""
    x: int
    y: int
    brightness: float
    image_id: Optional[str] = None
    contrast: float = 0.0  # コントラスト情報を追加
    last_updated: float = 0.0  # 最終更新時間


@dataclass
class MosaicGrid:
    """モザイクのグリッド全体"""
    width: int
    height: int
    cells: List[Cell]
    cell_size: tuple = (100, 100)


@dataclass
class Image:
    """アップロードされた画像"""
    id: str
    filename: str
    timestamp: datetime
    used: bool = False

    @classmethod
    def create(cls, filename: str) -> 'Image':
        """新しい画像インスタンスを作成"""
        return cls(
            id=uuid.uuid4().hex,
            filename=filename,
            timestamp=datetime.now(),
            used=False
        )


@dataclass
class MosaicUpdate:
    """モザイク更新情報"""
    updated_cell: Dict[str, int]
    file_id: str


@dataclass
class MosaicSettings:
    """モザイク生成の設定"""
    id: int
    grid_size: Tuple[int, int]
    logo_path: str
    title: str
    subtitle: str
    output_size: Tuple[int, int]
    regenerate_existing: bool = False

    @classmethod
    def create_default(cls) -> 'MosaicSettings':
        """デフォルト設定を作成"""
        import config
        return cls(
            id=1,  # 常に同じIDを使用
            grid_size=config.DEFAULT_GRID_SIZE,
            logo_path=str(config.SCHOOL_LOGO_PATH),
            title="校章モザイクアート",
            subtitle="みんなの思い出でつくる、私たちの学校",
            output_size=config.DEFAULT_OUTPUT_SIZE,
            regenerate_existing=False
        )
