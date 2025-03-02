"""
認証関連のミドルウェアと機能
"""
import base64
import functools
import hmac
import os
from typing import Any, Callable, List, Optional, Sequence, Union

from litestar import Request
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.middleware.authentication import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)
from litestar.middleware.base import DefineMiddleware

import config
from infrastructure.logger import get_logger

logger = get_logger("infrastructure.auth")


def requires_auth(handler: Callable) -> Callable:
    """Basic認証を要求するデコレータ"""
    @functools.wraps(handler)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        """認証チェックを行うラッパー関数"""
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break

        if not request and "request" in kwargs:
            request = kwargs["request"]
        if not request:
            raise ValueError("Request object not found in arguments")

        # 認証ヘッダーをチェック
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            raise NotAuthorizedException("認証が必要です")

        # Basic認証情報をデコード
        try:
            auth_decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, password = auth_decoded.split(":", 1)

            # 認証情報を検証
            if not authenticate(username, password):
                logger.warning(f"認証失敗: {username}")
                raise NotAuthorizedException("認証情報が無効です")

            logger.info(f"認証成功: {username}")
        except Exception as e:
            logger.error(f"認証エラー: {str(e)}", exc_info=True)
            raise NotAuthorizedException("認証情報が無効です")

        # 認証成功した場合、元のハンドラを実行
        return await handler(*args, **kwargs)

    return wrapper


def authenticate(username: str, password: str) -> bool:
    """ユーザー名とパスワードを検証"""
    admin_username = os.environ.get("ADMIN_USERNAME", config.ADMIN_USERNAME)
    admin_password = os.environ.get("ADMIN_PASSWORD", config.ADMIN_PASSWORD)

    # 安全な比較（タイミング攻撃対策）
    return hmac.compare_digest(username, admin_username) and \
           hmac.compare_digest(password, admin_password)


class BasicAuthMiddleware(AbstractAuthenticationMiddleware):
    """Basic認証を実装するミドルウェア"""

    def __init__(
        self,
        app: Any,
        exclude: Union[str, List[str], None] = None,
        exclude_from_auth_key: str = "exclude_from_auth",
        exclude_http_methods: Optional[Sequence[str]] = None,
        scopes: Optional[List[str]] = None,
        realm: str = "Mosaic Admin Panel"
    ) -> None:
        """Basic認証ミドルウェアを初期化

        Args:
            app: ASGIアプリケーション
            exclude: 認証から除外するパスやパターン
            exclude_from_auth_key: 認証から除外するためのルートオプションキー
            exclude_http_methods: 認証が不要なHTTPメソッド
            scopes: ミドルウェアが処理するASGIスコープ
            realm: Basic認証のレルム
        """
        super().__init__(
            app=app,
            exclude=exclude,
            exclude_from_auth_key=exclude_from_auth_key,
            exclude_http_methods=exclude_http_methods,
            scopes=scopes
        )
        self.logger = get_logger("infrastructure.BasicAuthMiddleware")
        self.realm = realm

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        """リクエストを認証して結果を返す

        Args:
            connection: ASGIコネクション

        Returns:
            認証結果

        Raises:
            NotAuthorizedException: 認証に失敗した場合
        """
        self.logger.debug(f"認証チェック: {connection.url.path}")

        # Authorizationヘッダーを取得
        auth_header = connection.headers.get("authorization")

        if not auth_header or not auth_header.startswith("Basic "):
            # 認証ヘッダーがない場合は401を返して認証を要求
            self.logger.warning(f"認証ヘッダーなし: {connection.url.path}")
            raise NotAuthorizedException(
                "Authentication required",
                headers={"WWW-Authenticate": f'Basic realm="{self.realm}"'}
            )

        # Basic認証情報をデコード
        try:
            auth_decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, password = auth_decoded.split(":", 1)

            # 認証情報を検証
            if not authenticate(username, password):
                self.logger.warning(f"認証失敗: {username}, path={connection.url.path}")
                raise NotAuthorizedException(
                    "Invalid credentials",
                    headers={"WWW-Authenticate": f'Basic realm="{self.realm}"'}
                )

            self.logger.debug(f"認証成功: {username}, path={connection.url.path}")

            # 成功時は認証結果を返す
            return AuthenticationResult(user={"username": username}, auth=auth_header)

        except Exception as e:
            self.logger.error(f"認証デコードエラー: {str(e)}", exc_info=True)
            raise NotAuthorizedException(
                "Invalid credentials",
                headers={"WWW-Authenticate": f'Basic realm="{self.realm}"'}
            )


def create_auth_middleware() -> DefineMiddleware:
    """認証ミドルウェアを初期化"""
    return DefineMiddleware(
        BasicAuthMiddleware,
        exclude=[
            r"^/(?!admin).*$",  # /admin で始まるパス以外は除外
        ],
        realm="MosaicAdminPanel"
    )
