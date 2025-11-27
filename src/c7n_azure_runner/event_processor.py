# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
イベントプロセッサーモジュール

Azure Event Grid イベントを解析し、対象ポリシーを特定します。
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from c7n.policy import Policy, PolicyCollection

log = logging.getLogger(__name__)


@dataclass
class ParsedEvent:
    """パース済みイベント"""

    event_id: str
    event_type: str
    subject: str
    operation_name: str
    resource_id: str
    event_time: str
    raw_data: dict[str, Any]

    @property
    def resource_provider(self) -> str:
        """リソースプロバイダー名を取得"""
        # operationName から抽出 (例: Microsoft.Storage/storageAccounts/write)
        parts = self.operation_name.rsplit("/", 1)
        if len(parts) >= 1:
            return parts[0]
        return ""

    @property
    def operation(self) -> str:
        """操作名を取得"""
        # operationName から抽出 (例: write)
        parts = self.operation_name.rsplit("/", 1)
        if len(parts) >= 2:
            return parts[1]
        return ""


class EventProcessor:
    """
    Azure Event Grid イベントプロセッサー

    Event Grid からのイベントを解析し、該当するポリシーを特定します。
    """

    def __init__(self):
        pass

    def decode_queue_message(self, message_content: str | bytes) -> dict[str, Any]:
        """
        Storage Queue メッセージをデコード

        Args:
            message_content: Base64 エンコードされたメッセージ

        Returns:
            デコードされた JSON オブジェクト
        """
        if isinstance(message_content, str):
            message_content = message_content.encode("utf-8")

        try:
            decoded = base64.b64decode(message_content).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            # Base64 でない場合は直接 JSON としてパース
            if isinstance(message_content, bytes):
                message_content = message_content.decode("utf-8")
            return json.loads(message_content)

    def parse_event(self, event_data: dict[str, Any]) -> ParsedEvent:
        """
        Event Grid イベントをパース

        Args:
            event_data: イベントデータ

        Returns:
            ParsedEvent オブジェクト
        """
        data = event_data.get("data", {})

        return ParsedEvent(
            event_id=event_data.get("id", ""),
            event_type=event_data.get("eventType", ""),
            subject=event_data.get("subject", ""),
            operation_name=data.get("operationName", ""),
            resource_id=data.get("resourceUri", event_data.get("subject", "")),
            event_time=event_data.get("eventTime", ""),
            raw_data=event_data,
        )

    def get_event_operations(self, events: list[str | dict]) -> list[str]:
        """
        イベント定義から操作名のリストを取得

        c7n_azure.azure_events.AzureEvents と同様のロジック

        Args:
            events: イベント定義のリスト

        Returns:
            操作名のリスト (例: ["Microsoft.Storage/storageAccounts/write"])
        """
        from c7n_azure.azure_events import AzureEvents

        return AzureEvents.get_event_operations(events)

    def find_matching_policies(
        self,
        event: ParsedEvent,
        policies: PolicyCollection,
    ) -> list[Policy]:
        """
        イベントにマッチするポリシーを検索

        Args:
            event: パース済みイベント
            policies: ポリシーコレクション

        Returns:
            マッチしたポリシーのリスト
        """
        matching = []
        operation_upper = event.operation_name.upper()

        for policy in policies:
            mode = policy.data.get("mode", {})
            policy_events = mode.get("events", [])

            if not policy_events:
                continue

            try:
                event_operations = self.get_event_operations(policy_events)
                event_operations_upper = [op.upper() for op in event_operations]

                if operation_upper in event_operations_upper:
                    log.info(
                        f"Policy '{policy.name}' matches event operation: {event.operation_name}"
                    )
                    matching.append(policy)

            except Exception as e:
                log.warning(f"Error checking policy {policy.name}: {e}")
                continue

        return matching

    def extract_resource_filter(self, event: ParsedEvent) -> dict[str, Any]:
        """
        イベントからリソースフィルター条件を抽出

        Args:
            event: パース済みイベント

        Returns:
            フィルター条件の辞書
        """
        return {
            "resource_id": event.resource_id,
            "resource_provider": event.resource_provider,
            "operation": event.operation,
        }
