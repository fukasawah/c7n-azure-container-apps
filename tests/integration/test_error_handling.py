# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
エラーハンドリングと境界条件の Integration テスト

異常系・境界条件を網羅し、堅牢性を検証する。
"""

from __future__ import annotations

import json

import pytest

from c7n_azure_runner.event_processor import EventProcessor
from c7n_azure_runner.policy_executor import PolicyExecutor

from .conftest import (
    FakePolicy,
    FakePolicyCollection,
    create_event_grid_event,
    create_event_policy,
    create_periodic_policy,
)


class TestErrorHandling:
    """
    エラーハンドリングの Integration テスト
    """

    def test_malformed_json_in_queue_message(self):
        """
        不正な JSON 文字列のデコードでエラー
        """
        # Arrange
        event_processor = EventProcessor()
        invalid_json = "{ invalid json content"

        # Act & Assert
        with pytest.raises(json.JSONDecodeError):
            event_processor.decode_queue_message(invalid_json)

    def test_malformed_base64_falls_back_to_plain_json(self):
        """
        Base64 デコードに失敗した場合、プレーン JSON として試行

        有効な JSON だが Base64 ではない場合のフォールバック。
        """
        # Arrange
        event_processor = EventProcessor()
        valid_json = json.dumps({"id": "plain-json-event", "data": {}})

        # Act
        decoded = event_processor.decode_queue_message(valid_json)

        # Assert
        assert decoded["id"] == "plain-json-event"

    def test_event_with_missing_fields(self):
        """
        必須フィールドが欠けたイベントでも parse_event は動作

        欠損フィールドは空文字列やデフォルト値になる。
        """
        # Arrange
        event_processor = EventProcessor()
        minimal_event = {"id": "minimal"}  # ほとんどのフィールドが欠損

        # Act
        parsed = event_processor.parse_event(minimal_event)

        # Assert
        assert parsed.event_id == "minimal"
        assert parsed.event_type == ""
        assert parsed.operation_name == ""
        assert parsed.subject == ""

    def test_policy_validation_failure_does_not_crash_collection(self):
        """
        validate() で例外を投げるポリシーがあっても他は処理可能

        現在の FakePolicy.validate() は常に成功するが、
        実際の実装では validation エラーが起きうる。
        """

        # Arrange
        class FailingValidatePolicy(FakePolicy):
            def validate(self) -> None:
                raise ValueError("Invalid policy configuration")

        good_policy = create_periodic_policy(name="good")
        bad_policy = FailingValidatePolicy(name="bad", data={})

        # Act - validate を個別に呼ぶパターン
        validated = []
        for p in [good_policy, bad_policy]:
            try:
                p.validate()
                validated.append(p)
            except ValueError:
                pass  # skip invalid

        # Assert
        assert len(validated) == 1
        assert validated[0].name == "good"


class TestBoundaryConditions:
    """
    境界条件の Integration テスト
    """

    def test_very_long_operation_name(self):
        """
        非常に長い operationName でも正常に処理
        """
        # Arrange
        event_processor = EventProcessor()
        long_operation = "Microsoft.LongProvider/" + "SubResource/" * 50 + "write"

        event = create_event_grid_event(operation_name=long_operation)

        # Act
        parsed = event_processor.parse_event(event)

        # Assert
        assert parsed.operation_name == long_operation
        assert parsed.operation == "write"

    def test_unicode_in_event_data(self):
        """
        イベントデータに Unicode 文字が含まれていても正常処理
        """
        # Arrange
        event_processor = EventProcessor()

        event = {
            "id": "unicode-event-日本語",
            "eventType": "Microsoft.Resources.ResourceWriteSuccess",
            "subject": "/subscriptions/sub/resourceGroups/日本語リソースグループ",
            "data": {
                "operationName": "Microsoft.Storage/storageAccounts/write",
                "resourceUri": "/subscriptions/sub/providers/Microsoft.Storage/日本語アカウント",
            },
            "eventTime": "2024-01-01T00:00:00Z",
        }

        # Act
        parsed = event_processor.parse_event(event)

        # Assert
        assert "日本語" in parsed.event_id
        assert "日本語リソースグループ" in parsed.subject

    def test_case_insensitive_operation_matching(self, _mock_azure_events):
        """
        operationName のマッチングは大文字小文字を区別しない

        Azure Event Grid は operationName を小文字/大文字混在で
        送ってくることがあるため、case-insensitive な比較が必要。
        """
        # Arrange
        event_processor = EventProcessor()

        # ポリシー側は大文字
        policy = create_event_policy(
            name="case-test",
            events=["MICROSOFT.STORAGE/STORAGEACCOUNTS/WRITE"],
        )
        policies = FakePolicyCollection(policies=[policy])

        # イベント側は小文字
        event = create_event_grid_event(operation_name="microsoft.storage/storageaccounts/write")

        # Act
        parsed = event_processor.parse_event(event)
        matching = event_processor.find_matching_policies(parsed, policies)

        # Assert - 現在の実装は upper() で比較しているのでマッチする
        assert len(matching) == 1

    def test_empty_events_in_policy_mode(self, _mock_azure_events):
        """
        mode.events が空のポリシーはどのイベントにもマッチしない
        """
        # Arrange
        event_processor = EventProcessor()

        policy = FakePolicy(
            name="no-events",
            data={
                "name": "no-events",
                "resource": "azure.storage",
                "mode": {
                    "type": "container-event",
                    "events": [],  # 空
                },
            },
        )
        policies = FakePolicyCollection(policies=[policy])

        event = create_event_grid_event()

        # Act
        parsed = event_processor.parse_event(event)
        matching = event_processor.find_matching_policies(parsed, policies)

        # Assert
        assert len(matching) == 0

    def test_policy_without_mode_is_skipped_for_event_matching(self, _mock_azure_events):
        """
        mode キーがないポリシーはイベントマッチングでスキップ
        """
        # Arrange
        event_processor = EventProcessor()

        no_mode_policy = FakePolicy(
            name="no-mode",
            data={"name": "no-mode", "resource": "azure.storage"},
        )
        policies = FakePolicyCollection(policies=[no_mode_policy])

        event = create_event_grid_event()

        # Act
        parsed = event_processor.parse_event(event)
        matching = event_processor.find_matching_policies(parsed, policies)

        # Assert
        assert len(matching) == 0


class TestExecutorStateManagement:
    """
    PolicyExecutor の状態管理テスト
    """

    def test_results_accumulate_across_executions(self):
        """
        複数回の execute_policy 呼び出しで結果が蓄積
        """
        # Arrange
        policy_executor = PolicyExecutor()

        policy1 = create_periodic_policy(name="p1")
        policy2 = create_periodic_policy(name="p2")

        # Act
        policy_executor.execute_policy(policy1)
        policy_executor.execute_policy(policy2)

        # Assert
        assert len(policy_executor.results) == 2
        summary = policy_executor.get_summary()
        assert summary["total_policies"] == 2

    def test_fresh_executor_has_empty_results(self):
        """
        新規インスタンスは空の結果リストを持つ
        """
        # Arrange & Act
        policy_executor = PolicyExecutor()

        # Assert
        assert policy_executor.results == []
        summary = policy_executor.get_summary()
        assert summary["total_policies"] == 0

    def test_summary_after_all_failures(self):
        """
        全ポリシーが失敗した場合のサマリ
        """
        # Arrange
        policy_executor = PolicyExecutor()

        failing1 = create_periodic_policy(name="fail1")
        failing1.run_exception = RuntimeError("Error 1")
        failing2 = create_periodic_policy(name="fail2")
        failing2.run_exception = RuntimeError("Error 2")

        policies = FakePolicyCollection(policies=[failing1, failing2])

        # Act
        policy_executor.execute_policies(policies)

        # Assert
        summary = policy_executor.get_summary()
        assert summary["succeeded"] == 0
        assert summary["failed"] == 2
        assert summary["total_resources"] == 0
