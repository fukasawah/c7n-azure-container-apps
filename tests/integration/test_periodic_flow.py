# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
定期実行（Periodic）フローの Integration テスト

PolicyCollection → mode フィルタ → PolicyExecutor.execute_policies の結合を検証。
"""

from __future__ import annotations

import pytest

from c7n_azure_runner.policy_executor import PolicyExecutor

from .conftest import (
    FakePolicy,
    FakePolicyCollection,
    create_event_policy,
    create_failing_policy,
    create_periodic_policy,
)


class TestPeriodicFlow:
    """
    定期実行フローの Integration テスト
    
    シナリオ: ポリシーロード → mode フィルタ → run() 実行
    """

    def test_execute_all_periodic_policies(self):
        """
        container-periodic モードの全ポリシーを実行

        定期実行では run() が呼ばれ、push() は呼ばれない。
        """
        # Arrange
        policy_executor = PolicyExecutor()
        
        policy1 = create_periodic_policy(
            name="vm-compliance",
            run_result=[{"id": "vm-1"}, {"id": "vm-2"}],
        )
        policy2 = create_periodic_policy(
            name="storage-audit",
            run_result=[{"id": "sa-1"}],
        )
        policies = FakePolicyCollection(policies=[policy1, policy2])
        
        # Act
        results = policy_executor.execute_policies(policies)
        
        # Assert
        assert len(results) == 2
        
        # run() が呼ばれた
        assert len(policy1.run_calls) == 1
        assert len(policy2.run_calls) == 1
        
        # push() は呼ばれていない
        assert len(policy1.push_calls) == 0
        assert len(policy2.push_calls) == 0
        
        summary = policy_executor.get_summary()
        assert summary["total_policies"] == 2
        assert summary["succeeded"] == 2
        assert summary["total_resources"] == 3  # 2 + 1

    def test_filter_periodic_from_mixed_policies(self):
        """
        混在ポリシーから container-periodic のみをフィルタして実行

        cli.py の run-scheduled と同等のロジックを検証。
        """
        # Arrange
        policy_executor = PolicyExecutor()
        
        periodic1 = create_periodic_policy(name="periodic-1")
        periodic2 = create_periodic_policy(name="periodic-2")
        event_policy = create_event_policy(name="event-only")
        
        all_policies = FakePolicyCollection(policies=[periodic1, event_policy, periodic2])
        
        # Act - cli.py と同等のフィルタ
        filtered = [
            p for p in all_policies
            if p.data.get("mode", {}).get("type") == "container-periodic"
        ]
        filtered_collection = FakePolicyCollection(policies=filtered)
        
        results = policy_executor.execute_policies(filtered_collection)
        
        # Assert
        assert len(filtered) == 2
        assert {p.name for p in filtered} == {"periodic-1", "periodic-2"}
        
        assert len(periodic1.run_calls) == 1
        assert len(periodic2.run_calls) == 1
        assert len(event_policy.run_calls) == 0
        assert len(event_policy.push_calls) == 0

    def test_partial_failure_continues_execution(self):
        """
        一部のポリシーが失敗しても、残りは実行される

        エラーは記録され、最終サマリに反映される。
        """
        # Arrange
        policy_executor = PolicyExecutor()
        
        success_policy = create_periodic_policy(
            name="success-policy",
            run_result=[{"id": "r1"}],
        )
        failing_policy = create_failing_policy(
            name="failing-policy",
            error_message="Simulated Azure error",
            fail_on="run",
        )
        another_success = create_periodic_policy(
            name="another-success",
            run_result=[{"id": "r2"}, {"id": "r3"}],
        )
        
        policies = FakePolicyCollection(
            policies=[success_policy, failing_policy, another_success]
        )
        
        # Act
        results = policy_executor.execute_policies(policies)
        
        # Assert
        assert len(results) == 3
        
        summary = policy_executor.get_summary()
        assert summary["succeeded"] == 2
        assert summary["failed"] == 1
        assert summary["total_resources"] == 3  # 成功した 2 つのポリシー分のみ
        
        # エラーメッセージが記録されている
        failed_result = next(r for r in summary["results"] if r["policy"] == "failing-policy")
        assert "Simulated Azure error" in failed_result["error"]

    def test_empty_policy_collection(self):
        """
        空のポリシーコレクションでも正常終了
        """
        # Arrange
        policy_executor = PolicyExecutor()
        policies = FakePolicyCollection(policies=[])
        
        # Act
        results = policy_executor.execute_policies(policies)
        
        # Assert
        assert len(results) == 0
        summary = policy_executor.get_summary()
        assert summary["total_policies"] == 0

    def test_execution_duration_is_recorded(self):
        """
        各ポリシーの実行時間が記録される
        """
        # Arrange
        policy_executor = PolicyExecutor()
        policy = create_periodic_policy(name="timed-policy")
        policies = FakePolicyCollection(policies=[policy])
        
        # Act
        results = policy_executor.execute_policies(policies)
        
        # Assert
        assert len(results) == 1
        assert results[0].duration_seconds >= 0
        assert results[0].start_time is not None
        assert results[0].end_time is not None
        assert results[0].end_time >= results[0].start_time


class TestMixedModeExecution:
    """
    異なるモードの組み合わせテスト
    """

    def test_execute_policies_respects_given_collection(self):
        """
        execute_policies は渡された PolicyCollection をそのまま処理する

        モードフィルタは呼び出し側の責任。
        """
        # Arrange
        policy_executor = PolicyExecutor()
        
        # container-event モードのポリシーを run() で実行しようとする
        # （本来は push() が適切だが、executor はモードを見ない）
        event_policy = create_event_policy(
            name="event-mode-but-run",
            run_result=[{"id": "forced-run"}],
        )
        policies = FakePolicyCollection(policies=[event_policy])
        
        # Act - event なしで実行 → run() が呼ばれる
        results = policy_executor.execute_policies(policies, event=None)
        
        # Assert
        assert len(results) == 1
        assert len(event_policy.run_calls) == 1
        assert len(event_policy.push_calls) == 0

    def test_execute_policies_with_event_calls_push(self):
        """
        event 引数を渡すと push() が呼ばれる

        execute_policies に event を渡すと、内部で execute_policy(policy, event)
        が呼ばれ、各ポリシーは push() で実行される。
        """
        # Arrange
        policy_executor = PolicyExecutor()
        
        policy = create_periodic_policy(name="periodic-but-push")
        policy.push_result = [{"id": "pushed"}]
        policies = FakePolicyCollection(policies=[policy])
        
        event = {"id": "evt", "data": {}}
        
        # Act - event ありで実行 → push() が呼ばれる
        results = policy_executor.execute_policies(policies, event=event)
        
        # Assert - event が渡されたので push() が呼ばれる
        assert len(policy.push_calls) == 1
        assert policy.push_calls[0]["event"]["id"] == "evt"
        assert len(policy.run_calls) == 0
