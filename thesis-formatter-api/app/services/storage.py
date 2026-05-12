"""MinIO 文件存储服务模块。

提供基于 MinIO 的文件上传、下载、删除、预签名 URL 生成等功能。
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class StorageService:
    """MinIO 文件存储服务。

    封装 MinIO 客户端，提供桶管理、文件 CRUD 及预签名 URL 等能力。
    所有方法均会捕获连接异常并记录日志，避免因存储层故障导致上游服务崩溃。
    """

    def __init__(self) -> None:
        self._client: Optional[Minio] = None
        self._bucket: str = settings.minio_bucket

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _get_client(self) -> Minio:
        """懒加载 MinIO 客户端，首次调用时建立连接。"""
        if self._client is None:
            try:
                self._client = Minio(
                    endpoint=settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    secure=settings.minio_secure,
                )
                logger.info(
                    "MinIO 客户端初始化成功 endpoint={} secure={}",
                    settings.minio_endpoint,
                    settings.minio_secure,
                )
            except Exception as exc:
                logger.error("MinIO 客户端初始化失败: {}", exc)
                raise
        return self._client

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def ensure_bucket(self) -> None:
        """确保存储桶已存在，若不存在则自动创建。"""
        try:
            client = self._get_client()
            if not client.bucket_exists(self._bucket):
                client.make_bucket(self._bucket)
                logger.info("存储桶 [{}] 创建成功", self._bucket)
            else:
                logger.debug("存储桶 [{}] 已存在", self._bucket)
        except S3Error as exc:
            logger.error("确保存储桶存在时发生 S3 错误: {}", exc)
            raise
        except Exception as exc:
            logger.error("确保存储桶存在时发生连接错误: {}", exc)
            raise

    def upload_file(self, file_data: bytes, object_key: str, content_type: str) -> str:
        """上传文件到 MinIO。

        Args:
            file_data: 文件二进制数据。
            object_key: 对象键（存储路径）。
            content_type: MIME 类型，如 ``application/pdf``。

        Returns:
            上传成功后返回 ``object_key``。

        Raises:
            ConnectionError: 与 MinIO 通信失败。
            S3Error: MinIO 服务端返回错误。
        """
        try:
            client = self._get_client()
            from io import BytesIO

            data_stream = BytesIO(file_data)
            client.put_object(
                bucket_name=self._bucket,
                object_name=object_key,
                data=data_stream,
                length=len(file_data),
                content_type=content_type,
            )
            logger.info("文件上传成功 bucket={} key={} size={}", self._bucket, object_key, len(file_data))
            return object_key
        except S3Error as exc:
            logger.error("文件上传 S3 错误 key={}: {}", object_key, exc)
            raise
        except Exception as exc:
            logger.error("文件上传连接错误 key={}: {}", object_key, exc)
            raise ConnectionError(f"无法连接 MinIO 服务: {exc}") from exc

    def download_file(self, object_key: str) -> bytes:
        """从 MinIO 下载文件。

        Args:
            object_key: 对象键。

        Returns:
            文件的二进制数据。

        Raises:
            FileNotFoundError: 对象不存在。
            ConnectionError: 与 MinIO 通信失败。
        """
        try:
            client = self._get_client()
            response = client.get_object(bucket_name=self._bucket, object_name=object_key)
            try:
                data = response.read()
            finally:
                response.close()
                response.release_conn()
            logger.info("文件下载成功 key={} size={}", object_key, len(data))
            return data
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                logger.warning("文件不存在 key={}", object_key)
                raise FileNotFoundError(f"对象 {object_key} 不存在") from exc
            logger.error("文件下载 S3 错误 key={}: {}", object_key, exc)
            raise
        except Exception as exc:
            logger.error("文件下载连接错误 key={}: {}", object_key, exc)
            raise ConnectionError(f"无法连接 MinIO 服务: {exc}") from exc

    def delete_file(self, object_key: str) -> None:
        """从 MinIO 删除文件。

        Args:
            object_key: 对象键。

        Raises:
            ConnectionError: 与 MinIO 通信失败。
        """
        try:
            client = self._get_client()
            client.remove_object(bucket_name=self._bucket, object_name=object_key)
            logger.info("文件删除成功 key={}", object_key)
        except S3Error as exc:
            logger.error("文件删除 S3 错误 key={}: {}", object_key, exc)
            raise
        except Exception as exc:
            logger.error("文件删除连接错误 key={}: {}", object_key, exc)
            raise ConnectionError(f"无法连接 MinIO 服务: {exc}") from exc

    def get_presigned_url(self, object_key: str, expires_hours: int = 1) -> str:
        """生成预签名下载 URL。

        Args:
            object_key: 对象键。
            expires_hours: URL 有效时长（小时），默认 1 小时。

        Returns:
            预签名下载 URL 字符串。

        Raises:
            ConnectionError: 与 MinIO 通信失败。
        """
        try:
            client = self._get_client()
            from datetime import timedelta

            url = client.presigned_get_object(
                bucket_name=self._bucket,
                object_name=object_key,
                expires=timedelta(hours=expires_hours),
            )
            logger.info("生成预签名 URL key={} expires={}h", object_key, expires_hours)
            return url
        except S3Error as exc:
            logger.error("生成预签名 URL S3 错误 key={}: {}", object_key, exc)
            raise
        except Exception as exc:
            logger.error("生成预签名 URL 连接错误 key={}: {}", object_key, exc)
            raise ConnectionError(f"无法连接 MinIO 服务: {exc}") from exc

    def file_exists(self, object_key: str) -> bool:
        """检查文件是否存在于 MinIO 中。

        Args:
            object_key: 对象键。

        Returns:
            存在返回 ``True``，否则返回 ``False``。
        """
        try:
            client = self._get_client()
            client.stat_object(bucket_name=self._bucket, object_name=object_key)
            logger.debug("文件存在 key={}", object_key)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                logger.debug("文件不存在 key={}", object_key)
                return False
            logger.error("检查文件存在性 S3 错误 key={}: {}", object_key, exc)
            return False
        except Exception as exc:
            logger.error("检查文件存在性连接错误 key={}: {}", object_key, exc)
            return False


# ------------------------------------------------------------------
# 全局单例
# ------------------------------------------------------------------

_storage_instance: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """获取 StorageService 全局单例。

    首次调用时创建实例，后续调用返回同一实例。
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageService()
        logger.info("StorageService 全局单例已创建")
    return _storage_instance
