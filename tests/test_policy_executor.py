# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""policy_executor モジュールのテスト"""

from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from c7n_azure_runner.policy_executor import ExecutionResult, PolicyExecutor


class TestExecutionResult:
    """ExecutionResult のテスト"""

    def test_duration_seconds(self):
        """実行時間計算のテスト"""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 1, 0, 0, 30)

        result = ExecutionResult(
            policy_name="test-policy",
            success=True,
            resource_count=5,
            start_time=start,
            end_time=end,
        )

        assert result.duration_seconds == 30.0

    def test_error_field(self):
        """エラーフィールドのテスト"""
        result = ExecutionResult(
            policy_name="test-policy",
            success=False,
            resource_count=0,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error="Test error message",
        )

        assert result.error == "Test error message"


class TestPolicyExecutor:
    """PolicyExecutor のテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.executor = PolicyExecutor()

    def test_initial_state(self):
        """初期状態のテスト"""
        assert self.executor.results == []

    def test_execute_policy_success(self):
        """ポリシー実行成功のテスト"""
        # モックポリシー
        mock_policy = mock.MagicMock()
        mock_policy.name = "test-policy"
        mock_policy.run.return_value = [{"id": "resource1"}, {"id": "resource2"}]

        result = self.executor.execute_policy(mock_policy)

        assert result.success is True
        assert result.policy_name == "test-policy"
        assert result.resource_count == 2
        assert result.error is None
        assert len(self.executor.results) == 1

    def test_execute_policy_failure(self):
        """ポリシー実行失敗のテスト"""
        mock_policy = mock.MagicMock()
        mock_policy.name = "test-policy"
        mock_policy.run.side_effect = Exception("Test error")

        result = self.executor.execute_policy(mock_policy)

        assert result.success is False
        assert result.policy_name == "test-policy"
        assert result.resource_count == 0
        assert "Test error" in result.error

    def test_execute_policy_with_event(self):
        """イベント駆動実行のテスト"""
        mock_policy = mock.MagicMock()
        mock_policy.name = "test-policy"
        mock_policy.push.return_value = [{"id": "resource1"}]

        event = {"id": "event-123", "data": {}}
        result = self.executor.execute_policy(mock_policy, event=event)

        assert result.success is True
        mock_policy.push.assert_called_once_with(event, None)

    def test_execute_policy_dryrun_sets_flag_and_logs(self, caplog):
        """dryrun 実行時にオプション設定とログ出力が行われる"""
        mock_policy = mock.MagicMock()
        mock_policy.name = "dry-policy"
        mock_policy.run.return_value = []
        mock_policy.options = SimpleNamespace(dryrun=False)

        executor = PolicyExecutor(dryrun=True)

        with caplog.at_level("INFO"):
            executor.execute_policy(mock_policy)

        assert mock_policy.options.dryrun is True
        assert any(
            "dry-policy" in record.message and "DRYRUN" in record.message
            for record in caplog.records
        )

    def test_execute_policies(self):
        """複数ポリシー実行のテスト"""
        mock_policies = [mock.MagicMock(), mock.MagicMock()]
        mock_policies[0].name = "policy-1"
        mock_policies[0].run.return_value = [{"id": "r1"}]
        mock_policies[1].name = "policy-2"
        mock_policies[1].run.return_value = [{"id": "r2"}, {"id": "r3"}]

        results = self.executor.execute_policies(mock_policies)

        assert len(results) == 2
        assert results[0].policy_name == "policy-1"
        assert results[1].policy_name == "policy-2"

    def test_get_summary(self):
        """サマリー取得のテスト"""
        # いくつかの結果を追加
        self.executor.results = [
            ExecutionResult(
                policy_name="policy-1",
                success=True,
                resource_count=5,
                start_time=datetime(2024, 1, 1, 0, 0, 0),
                end_time=datetime(2024, 1, 1, 0, 0, 10),
            ),
            ExecutionResult(
                policy_name="policy-2",
                success=False,
                resource_count=0,
                start_time=datetime(2024, 1, 1, 0, 0, 10),
                end_time=datetime(2024, 1, 1, 0, 0, 15),
                error="Failed",
            ),
            ExecutionResult(
                policy_name="policy-3",
                success=True,
                resource_count=3,
                start_time=datetime(2024, 1, 1, 0, 0, 15),
                end_time=datetime(2024, 1, 1, 0, 0, 20),
            ),
        ]

        summary = self.executor.get_summary()

        assert summary["total_policies"] == 3
        assert summary["succeeded"] == 2
        assert summary["failed"] == 1
        assert summary["total_resources"] == 8
        assert summary["total_duration_seconds"] == 20.0
        assert len(summary["results"]) == 3
