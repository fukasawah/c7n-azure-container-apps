# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
event_processor モジュールのテスト
"""

import json

from c7n_azure_runner.event_processor import EventProcessor, ParsedEvent


class TestEventProcessor:
    """EventProcessor のテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.processor = EventProcessor()

    def test_decode_queue_message_base64(self):
        """Base64 エンコードされたメッセージのデコードテスト"""
        import base64

        original = {"test": "data", "id": "123"}
        encoded = base64.b64encode(json.dumps(original).encode("utf-8"))

        result = self.processor.decode_queue_message(encoded)
        assert result == original

    def test_decode_queue_message_plain_json(self):
        """プレーン JSON メッセージのデコードテスト"""
        original = {"test": "data", "id": "123"}
        json_str = json.dumps(original)

        result = self.processor.decode_queue_message(json_str)
        assert result == original

    def test_parse_event(self):
        """イベントパースのテスト"""
        event_data = {
            "id": "event-123",
            "eventType": "Microsoft.Resources.ResourceWriteSuccess",
            "subject": "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/test",
            "eventTime": "2024-01-01T00:00:00Z",
            "data": {
                "operationName": "Microsoft.Storage/storageAccounts/write",
                "resourceUri": "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/test",
            },
        }

        parsed = self.processor.parse_event(event_data)

        assert parsed.event_id == "event-123"
        assert parsed.event_type == "Microsoft.Resources.ResourceWriteSuccess"
        assert parsed.operation_name == "Microsoft.Storage/storageAccounts/write"
        assert "Microsoft.Storage/storageAccounts" in parsed.resource_id
        assert parsed.event_time == "2024-01-01T00:00:00Z"


class TestParsedEvent:
    """ParsedEvent のテスト"""

    def test_resource_provider(self):
        """リソースプロバイダー抽出のテスト"""
        event = ParsedEvent(
            event_id="123",
            event_type="test",
            subject="test",
            operation_name="Microsoft.Storage/storageAccounts/write",
            resource_id="test",
            event_time="2024-01-01",
            raw_data={},
        )
        assert event.resource_provider == "Microsoft.Storage/storageAccounts"

    def test_operation(self):
        """操作名抽出のテスト"""
        event = ParsedEvent(
            event_id="123",
            event_type="test",
            subject="test",
            operation_name="Microsoft.Storage/storageAccounts/write",
            resource_id="test",
            event_time="2024-01-01",
            raw_data={},
        )
        assert event.operation == "write"
