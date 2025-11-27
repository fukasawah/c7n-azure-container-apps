# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
Storage Queue ハンドラー

Azure Storage Queue からメッセージを取得・処理します。
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from azure.storage.queue import QueueMessage

log = logging.getLogger(__name__)


class QueueHandler:
    """
    Azure Storage Queue ハンドラー

    Managed Identity を使用して Storage Queue に接続し、
    メッセージの取得・削除を行います。
    """

    def __init__(
        self,
        storage_account_name: str,
        queue_name: str,
        use_managed_identity: bool = True,
    ):
        """
        Args:
            storage_account_name: ストレージアカウント名
            queue_name: キュー名
            use_managed_identity: Managed Identity を使用するか
        """
        self.storage_account_name = storage_account_name
        self.queue_name = queue_name
        self.use_managed_identity = use_managed_identity
        self._queue_client = None

    @property
    def queue_url(self) -> str:
        """キューの URL を取得"""
        return f"https://{self.storage_account_name}.queue.core.windows.net/{self.queue_name}"

    def _get_queue_client(self):
        """Queue クライアントを取得"""
        if self._queue_client is None:
            from azure.storage.queue import QueueClient

            if self.use_managed_identity:
                from azure.identity import DefaultAzureCredential

                credential = DefaultAzureCredential()
                self._queue_client = QueueClient(
                    account_url=f"https://{self.storage_account_name}.queue.core.windows.net",
                    queue_name=self.queue_name,
                    credential=credential,
                )
            else:
                # 接続文字列を使用（環境変数から）
                import os

                connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
                self._queue_client = QueueClient.from_connection_string(
                    connection_string,
                    queue_name=self.queue_name,
                )

        return self._queue_client

    def receive_messages(
        self,
        max_messages: int = 5,
        visibility_timeout: int = 300,
    ) -> Generator[QueueMessage]:
        """
        キューからメッセージを受信

        Args:
            max_messages: 一度に取得する最大メッセージ数
            visibility_timeout: 可視性タイムアウト（秒）

        Yields:
            QueueMessage オブジェクト
        """
        client = self._get_queue_client()

        messages = client.receive_messages(
            max_messages=max_messages,
            visibility_timeout=visibility_timeout,
        )

        for message in messages:
            log.debug(f"Received message: {message.id}")
            yield message

    def delete_message(self, message: QueueMessage) -> None:
        """
        メッセージを削除

        Args:
            message: 削除するメッセージ
        """
        client = self._get_queue_client()
        client.delete_message(message)
        log.debug(f"Deleted message: {message.id}")

    def get_message_content(self, message: QueueMessage) -> str:
        """
        メッセージの内容を取得

        Args:
            message: メッセージ

        Returns:
            メッセージ内容（文字列）
        """
        return message.content

    def process_single_message(self) -> dict[str, Any] | None:
        """
        単一メッセージを処理

        Returns:
            メッセージ内容（JSON）、メッセージがない場合は None
        """

        from c7n_azure_runner.event_processor import EventProcessor

        processor = EventProcessor()

        for message in self.receive_messages(max_messages=1):
            try:
                content = self.get_message_content(message)
                event_data = processor.decode_queue_message(content)
                self.delete_message(message)
                return event_data
            except Exception as e:
                log.error(f"Failed to process message: {e}")
                # メッセージは削除せず、リトライに回す
                raise

        return None

    def peek_queue_length(self) -> int:
        """
        キューの長さを確認（メッセージを消費しない）

        Returns:
            キュー内のメッセージ数（概算）
        """
        client = self._get_queue_client()
        properties = client.get_queue_properties()
        return properties.approximate_message_count or 0
