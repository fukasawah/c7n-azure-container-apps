# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
Integration テスト用フィクスチャとテストダブル

c7n-azure / Azure 実体への依存を切り、コンポーネント間結合をテスト可能にする。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator
from unittest import mock

import pytest


# =============================================================================
# Fake Policy - c7n Policy の振る舞いをシミュレート
# =============================================================================


@dataclass
class FakePolicy:
    """
    c7n Policy のテストダブル
    
    run() / push() の振る舞いを制御でき、呼び出し履歴を記録する。
    """
    
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    
    # 動作制御
    run_result: list[dict[str, Any]] = field(default_factory=list)
    push_result: list[dict[str, Any]] = field(default_factory=list)
    run_exception: Exception | None = None
    push_exception: Exception | None = None
    
    # 呼び出し履歴
    run_calls: list[dict[str, Any]] = field(default_factory=list)
    push_calls: list[dict[str, Any]] = field(default_factory=list)
    
    def run(self) -> list[dict[str, Any]]:
        """Pull 型実行（定期実行用）"""
        self.run_calls.append({"called": True})
        if self.run_exception:
            raise self.run_exception
        return self.run_result
    
    def push(self, event: dict[str, Any], context: Any) -> list[dict[str, Any]]:
        """Push 型実行（イベント駆動用）"""
        self.push_calls.append({"event": event, "context": context})
        if self.push_exception:
            raise self.push_exception
        return self.push_result
    
    def validate(self) -> None:
        """バリデーション（常に成功）"""
        pass


@dataclass
class FakePolicyCollection:
    """
    c7n PolicyCollection のテストダブル
    
    イテレート可能な Policy のコンテナ。
    """
    
    policies: list[FakePolicy] = field(default_factory=list)
    options: Any = None
    
    def __iter__(self) -> Iterator[FakePolicy]:
        return iter(self.policies)
    
    def __len__(self) -> int:
        return len(self.policies)
    
    def __bool__(self) -> bool:
        return len(self.policies) > 0


# =============================================================================
# テスト用ポリシーファクトリー
# =============================================================================


def create_event_policy(
    name: str,
    resource_type: str = "azure.storage",
    events: list[str] | None = None,
    run_result: list[dict] | None = None,
    push_result: list[dict] | None = None,
) -> FakePolicy:
    """
    イベント駆動型ポリシーを生成
    
    Args:
        name: ポリシー名
        resource_type: リソースタイプ
        events: イベント操作名のリスト (例: ["Microsoft.Storage/storageAccounts/write"])
        run_result: run() の戻り値
        push_result: push() の戻り値
    
    Returns:
        FakePolicy インスタンス
    """
    if events is None:
        events = ["Microsoft.Storage/storageAccounts/write"]
    
    return FakePolicy(
        name=name,
        data={
            "name": name,
            "resource": resource_type,
            "mode": {
                "type": "container-event",
                "events": events,
            },
        },
        run_result=run_result or [],
        push_result=push_result or [{"id": "matched-resource"}],
    )


def create_periodic_policy(
    name: str,
    resource_type: str = "azure.vm",
    run_result: list[dict] | None = None,
) -> FakePolicy:
    """
    定期実行型ポリシーを生成
    
    Args:
        name: ポリシー名
        resource_type: リソースタイプ
        run_result: run() の戻り値
    
    Returns:
        FakePolicy インスタンス
    """
    return FakePolicy(
        name=name,
        data={
            "name": name,
            "resource": resource_type,
            "mode": {
                "type": "container-periodic",
            },
        },
        run_result=run_result or [{"id": "resource-1"}, {"id": "resource-2"}],
    )


def create_failing_policy(
    name: str,
    error_message: str = "Simulated policy failure",
    fail_on: str = "run",  # "run" or "push"
) -> FakePolicy:
    """
    実行時にエラーを起こすポリシーを生成
    
    Args:
        name: ポリシー名
        error_message: エラーメッセージ
        fail_on: どの実行メソッドで失敗するか ("run" or "push")
    
    Returns:
        FakePolicy インスタンス
    """
    policy = FakePolicy(
        name=name,
        data={
            "name": name,
            "resource": "azure.vm",
            "mode": {"type": "container-periodic"},
        },
    )
    
    if fail_on == "run":
        policy.run_exception = RuntimeError(error_message)
    else:
        policy.push_exception = RuntimeError(error_message)
    
    return policy


# =============================================================================
# テスト用イベントファクトリー
# =============================================================================


def create_event_grid_event(
    operation_name: str = "Microsoft.Storage/storageAccounts/write",
    event_id: str = "test-event-123",
    resource_id: str = "/subscriptions/sub-123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/testaccount",
    event_type: str = "Microsoft.Resources.ResourceWriteSuccess",
) -> dict[str, Any]:
    """
    Azure Event Grid イベントを生成
    
    Args:
        operation_name: 操作名
        event_id: イベントID
        resource_id: リソースID
        event_type: イベントタイプ
    
    Returns:
        Event Grid イベント JSON
    """
    return {
        "id": event_id,
        "eventType": event_type,
        "subject": resource_id,
        "eventTime": "2024-01-01T00:00:00Z",
        "data": {
            "operationName": operation_name,
            "resourceUri": resource_id,
        },
    }


def create_queue_message_content(event: dict[str, Any], encode_base64: bool = True) -> str:
    """
    Queue メッセージとしてのイベントコンテンツを生成
    
    Args:
        event: イベントデータ
        encode_base64: Base64 エンコードするか
    
    Returns:
        メッセージコンテンツ文字列
    """
    import base64
    import json
    
    json_str = json.dumps(event)
    if encode_base64:
        return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    return json_str


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def fake_policy_collection() -> Callable[..., FakePolicyCollection]:
    """FakePolicyCollection を生成するファクトリ fixture"""
    def factory(*policies: FakePolicy) -> FakePolicyCollection:
        return FakePolicyCollection(policies=list(policies))
    return factory


@pytest.fixture
def event_processor():
    """EventProcessor インスタンス"""
    from c7n_azure_runner.event_processor import EventProcessor
    return EventProcessor()


@pytest.fixture
def policy_executor():
    """PolicyExecutor インスタンス"""
    from c7n_azure_runner.policy_executor import PolicyExecutor
    return PolicyExecutor()


@pytest.fixture
def mock_azure_events():
    """
    AzureEvents.get_event_operations をモックする fixture
    
    c7n-azure 依存を回避し、テスト用の操作名マッピングを提供。
    """
    def mock_get_event_operations(events: list) -> list[str]:
        """
        events 配列から操作名を抽出
        
        テスト用簡易実装: 文字列はそのまま、dict は resourceProvider + eventName を結合
        """
        operations = []
        for event in events:
            if isinstance(event, str):
                operations.append(event)
            elif isinstance(event, dict):
                # 実際の AzureEvents と同様のロジック
                provider = event.get("resourceProvider", "")
                event_name = event.get("event", "")
                if provider and event_name:
                    operations.append(f"{provider}/{event_name}")
        return operations
    
    with mock.patch(
        "c7n_azure_runner.event_processor.EventProcessor.get_event_operations",
        side_effect=mock_get_event_operations,
    ) as mocked:
        yield mocked
