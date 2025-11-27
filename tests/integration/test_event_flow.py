# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
イベント駆動フローの Integration テスト

EventProcessor → PolicyExecutor の結合を検証する。
外部リソース（Azure / c7n-azure）への依存なしでテスト可能。
"""

from __future__ import annotations

import pytest

from c7n_azure_runner.event_processor import EventProcessor
from c7n_azure_runner.policy_executor import PolicyExecutor

from .conftest import (
    FakePolicy,
    FakePolicyCollection,
    create_event_grid_event,
    create_event_policy,
    create_failing_policy,
    create_queue_message_content,
)


class TestEventDrivenFlow:
    """
    イベント駆動フローの Integration テスト
    
    シナリオ: Queue/EventGrid からイベント受信 → 対象ポリシー特定 → push 実行
    """

    def test_single_event_matches_single_policy(self, mock_azure_events):
        """
        単一イベント → 単一ポリシーにマッチ → push 実行

        最も基本的なイベント駆動フロー。
        イベントの operationName がポリシーの events に含まれる場合、
        そのポリシーの push() が呼ばれることを検証。
        """
        # Arrange
        event_processor = EventProcessor()
        policy_executor = PolicyExecutor()
        
        policy = create_event_policy(
            name="storage-write-policy",
            events=["Microsoft.Storage/storageAccounts/write"],
            push_result=[{"id": "storage-1"}],
        )
        policies = FakePolicyCollection(policies=[policy])
        
        event = create_event_grid_event(
            operation_name="Microsoft.Storage/storageAccounts/write",
            event_id="evt-001",
        )
        
        # Act
        parsed_event = event_processor.parse_event(event)
        matching = event_processor.find_matching_policies(parsed_event, policies)
        
        for matched_policy in matching:
            policy_executor.execute_policy(matched_policy, event=parsed_event.raw_data)
        
        # Assert
        assert len(matching) == 1
        assert matching[0].name == "storage-write-policy"
        
        # push が正しいイベントで呼ばれた
        assert len(policy.push_calls) == 1
        assert policy.push_calls[0]["event"]["id"] == "evt-001"
        
        # run は呼ばれていない
        assert len(policy.run_calls) == 0
        
        # 実行結果サマリが正しい
        summary = policy_executor.get_summary()
        assert summary["total_policies"] == 1
        assert summary["succeeded"] == 1
        assert summary["total_resources"] == 1

    def test_single_event_matches_multiple_policies(self, mock_azure_events):
        """
        単一イベント → 複数ポリシーにマッチ

        同一の events を持つポリシーが複数ある場合、
        すべてのポリシーが実行される。
        """
        # Arrange
        event_processor = EventProcessor()
        policy_executor = PolicyExecutor()
        
        policy1 = create_event_policy(
            name="storage-audit",
            events=["Microsoft.Storage/storageAccounts/write"],
            push_result=[{"id": "r1"}],
        )
        policy2 = create_event_policy(
            name="storage-tag",
            events=["Microsoft.Storage/storageAccounts/write"],
            push_result=[{"id": "r2"}, {"id": "r3"}],
        )
        policies = FakePolicyCollection(policies=[policy1, policy2])
        
        event = create_event_grid_event(
            operation_name="Microsoft.Storage/storageAccounts/write"
        )
        
        # Act
        parsed_event = event_processor.parse_event(event)
        matching = event_processor.find_matching_policies(parsed_event, policies)
        
        for matched_policy in matching:
            policy_executor.execute_policy(matched_policy, event=parsed_event.raw_data)
        
        # Assert
        assert len(matching) == 2
        assert {p.name for p in matching} == {"storage-audit", "storage-tag"}
        
        # 両方の push が呼ばれた
        assert len(policy1.push_calls) == 1
        assert len(policy2.push_calls) == 1
        
        summary = policy_executor.get_summary()
        assert summary["total_policies"] == 2
        assert summary["succeeded"] == 2
        assert summary["total_resources"] == 3  # 1 + 2

    def test_event_matches_no_policy(self, mock_azure_events):
        """
        イベント → どのポリシーにもマッチしない

        イベントの operationName がどのポリシーの events にも
        含まれない場合、何も実行されない。
        """
        # Arrange
        event_processor = EventProcessor()
        policy_executor = PolicyExecutor()
        
        policy = create_event_policy(
            name="storage-policy",
            events=["Microsoft.Storage/storageAccounts/write"],
        )
        policies = FakePolicyCollection(policies=[policy])
        
        # 異なる操作名のイベント
        event = create_event_grid_event(
            operation_name="Microsoft.Compute/virtualMachines/write"
        )
        
        # Act
        parsed_event = event_processor.parse_event(event)
        matching = event_processor.find_matching_policies(parsed_event, policies)
        
        # Assert
        assert len(matching) == 0
        assert len(policy.push_calls) == 0
        assert policy_executor.get_summary()["total_policies"] == 0

    def test_event_selective_matching(self, mock_azure_events):
        """
        複数ポリシー中、一部のみがイベントにマッチ

        異なる events を持つポリシーが混在する場合、
        マッチするものだけが選択・実行される。
        """
        # Arrange
        event_processor = EventProcessor()
        policy_executor = PolicyExecutor()
        
        storage_policy = create_event_policy(
            name="storage-policy",
            events=["Microsoft.Storage/storageAccounts/write"],
        )
        vm_policy = create_event_policy(
            name="vm-policy",
            events=["Microsoft.Compute/virtualMachines/write"],
        )
        policies = FakePolicyCollection(policies=[storage_policy, vm_policy])
        
        event = create_event_grid_event(
            operation_name="Microsoft.Storage/storageAccounts/write"
        )
        
        # Act
        parsed_event = event_processor.parse_event(event)
        matching = event_processor.find_matching_policies(parsed_event, policies)
        
        for matched_policy in matching:
            policy_executor.execute_policy(matched_policy, event=parsed_event.raw_data)
        
        # Assert
        assert len(matching) == 1
        assert matching[0].name == "storage-policy"
        
        assert len(storage_policy.push_calls) == 1
        assert len(vm_policy.push_calls) == 0

    def test_push_execution_failure_is_recorded(self, mock_azure_events):
        """
        push 実行中のエラーが ExecutionResult に記録される
        """
        # Arrange
        event_processor = EventProcessor()
        policy_executor = PolicyExecutor()
        
        failing_policy = create_event_policy(
            name="failing-policy",
            events=["Microsoft.Storage/storageAccounts/write"],
        )
        failing_policy.push_exception = RuntimeError("Azure API throttled")
        
        policies = FakePolicyCollection(policies=[failing_policy])
        
        event = create_event_grid_event(
            operation_name="Microsoft.Storage/storageAccounts/write"
        )
        
        # Act
        parsed_event = event_processor.parse_event(event)
        matching = event_processor.find_matching_policies(parsed_event, policies)
        
        for matched_policy in matching:
            policy_executor.execute_policy(matched_policy, event=parsed_event.raw_data)
        
        # Assert
        summary = policy_executor.get_summary()
        assert summary["failed"] == 1
        assert summary["succeeded"] == 0
        assert "Azure API throttled" in summary["results"][0]["error"]


class TestQueueMessageDecoding:
    """
    Queue メッセージデコードの Integration テスト
    
    Storage Queue から受信したメッセージを EventProcessor で処理するフロー。
    """

    def test_base64_encoded_message(self):
        """
        Base64 エンコードされた Queue メッセージのデコード
        """
        # Arrange
        event_processor = EventProcessor()
        
        original_event = create_event_grid_event(
            operation_name="Microsoft.Storage/storageAccounts/write",
            event_id="queue-evt-001",
        )
        message_content = create_queue_message_content(original_event, encode_base64=True)
        
        # Act
        decoded = event_processor.decode_queue_message(message_content)
        
        # Assert
        assert decoded["id"] == "queue-evt-001"
        assert decoded["data"]["operationName"] == "Microsoft.Storage/storageAccounts/write"

    def test_plain_json_message(self):
        """
        プレーン JSON の Queue メッセージのデコード
        """
        # Arrange
        event_processor = EventProcessor()
        
        original_event = create_event_grid_event(
            operation_name="Microsoft.Compute/virtualMachines/delete",
            event_id="queue-evt-002",
        )
        message_content = create_queue_message_content(original_event, encode_base64=False)
        
        # Act
        decoded = event_processor.decode_queue_message(message_content)
        
        # Assert
        assert decoded["id"] == "queue-evt-002"
        assert decoded["data"]["operationName"] == "Microsoft.Compute/virtualMachines/delete"

    def test_full_queue_to_execution_flow(self, mock_azure_events):
        """
        Queue メッセージ → デコード → イベント解析 → ポリシー実行の全フロー
        """
        # Arrange
        event_processor = EventProcessor()
        policy_executor = PolicyExecutor()
        
        policy = create_event_policy(
            name="queue-triggered-policy",
            events=["Microsoft.Storage/storageAccounts/write"],
            push_result=[{"id": "processed"}],
        )
        policies = FakePolicyCollection(policies=[policy])
        
        # Queue に入る形式のメッセージを作成
        original_event = create_event_grid_event(
            operation_name="Microsoft.Storage/storageAccounts/write",
            event_id="queue-full-flow",
        )
        message_content = create_queue_message_content(original_event, encode_base64=True)
        
        # Act - Queue ハンドラーの役割をシミュレート
        event_dict = event_processor.decode_queue_message(message_content)
        parsed_event = event_processor.parse_event(event_dict)
        matching = event_processor.find_matching_policies(parsed_event, policies)
        
        for matched_policy in matching:
            policy_executor.execute_policy(matched_policy, event=parsed_event.raw_data)
        
        # Assert
        assert len(matching) == 1
        assert len(policy.push_calls) == 1
        assert policy.push_calls[0]["event"]["id"] == "queue-full-flow"
        
        summary = policy_executor.get_summary()
        assert summary["succeeded"] == 1


class TestEventParsing:
    """
    イベント解析の詳細テスト
    """

    def test_parsed_event_properties(self):
        """
        ParsedEvent の各プロパティが正しく抽出される
        """
        # Arrange
        event_processor = EventProcessor()
        
        event = create_event_grid_event(
            operation_name="Microsoft.Storage/storageAccounts/blobServices/containers/write",
            event_id="parse-test",
            resource_id="/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Storage/storageAccounts/sa1",
            event_type="Microsoft.Resources.ResourceWriteSuccess",
        )
        
        # Act
        parsed = event_processor.parse_event(event)
        
        # Assert
        assert parsed.event_id == "parse-test"
        assert parsed.event_type == "Microsoft.Resources.ResourceWriteSuccess"
        assert parsed.operation_name == "Microsoft.Storage/storageAccounts/blobServices/containers/write"
        assert parsed.resource_id == "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Storage/storageAccounts/sa1"
        assert parsed.resource_provider == "Microsoft.Storage/storageAccounts/blobServices/containers"
        assert parsed.operation == "write"

    def test_extract_resource_filter(self):
        """
        イベントからリソースフィルター条件を抽出
        """
        # Arrange
        event_processor = EventProcessor()
        
        event = create_event_grid_event(
            operation_name="Microsoft.Compute/virtualMachines/delete",
            resource_id="/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm1",
        )
        
        # Act
        parsed = event_processor.parse_event(event)
        filter_conditions = event_processor.extract_resource_filter(parsed)
        
        # Assert
        assert filter_conditions["resource_id"] == "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm1"
        assert filter_conditions["resource_provider"] == "Microsoft.Compute/virtualMachines"
        assert filter_conditions["operation"] == "delete"
