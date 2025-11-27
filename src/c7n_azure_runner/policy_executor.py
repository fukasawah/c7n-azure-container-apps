# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
ポリシー実行エンジンモジュール

Cloud Custodian ポリシーの実行を管理します。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from c7n.policy import Policy, PolicyCollection

log = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """ポリシー実行結果"""

    policy_name: str
    success: bool
    resource_count: int
    start_time: datetime
    end_time: datetime
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        """実行時間（秒）"""
        return (self.end_time - self.start_time).total_seconds()


class PolicyExecutor:
    """
    Cloud Custodian ポリシー実行エンジン

    ポリシーの実行と結果の収集を行います。
    """

    def __init__(self):
        self.results: list[ExecutionResult] = []

    def execute_policy(
        self,
        policy: Policy,
        event: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        単一ポリシーを実行

        Args:
            policy: 実行するポリシー
            event: イベントデータ（イベント駆動実行時）

        Returns:
            ExecutionResult オブジェクト
        """
        start_time = datetime.now()
        log.info(f"Executing policy: {policy.name}")

        try:
            if event:
                # イベント駆動実行
                resources = policy.push(event, None)
            else:
                # プル実行（定期実行）
                resources = policy.run()

            resource_count = len(resources) if resources else 0
            end_time = datetime.now()

            result = ExecutionResult(
                policy_name=policy.name,
                success=True,
                resource_count=resource_count,
                start_time=start_time,
                end_time=end_time,
            )

            log.info(
                f"Policy {policy.name} completed: "
                f"{resource_count} resources, "
                f"{result.duration_seconds:.2f}s"
            )

        except Exception as e:
            end_time = datetime.now()
            result = ExecutionResult(
                policy_name=policy.name,
                success=False,
                resource_count=0,
                start_time=start_time,
                end_time=end_time,
                error=str(e),
            )
            log.exception(f"Policy {policy.name} failed: {e}")

        self.results.append(result)
        return result

    def execute_policies(
        self,
        policies: PolicyCollection,
        event: dict[str, Any] | None = None,
    ) -> list[ExecutionResult]:
        """
        複数ポリシーを実行

        Args:
            policies: 実行するポリシーコレクション
            event: イベントデータ（イベント駆動実行時）

        Returns:
            ExecutionResult のリスト
        """
        results = []
        for policy in policies:
            result = self.execute_policy(policy, event)
            results.append(result)
        return results

    def get_summary(self) -> dict[str, Any]:
        """実行結果のサマリーを取得"""
        total = len(self.results)
        succeeded = sum(1 for r in self.results if r.success)
        failed = total - succeeded
        total_resources = sum(r.resource_count for r in self.results)
        total_duration = sum(r.duration_seconds for r in self.results)

        return {
            "total_policies": total,
            "succeeded": succeeded,
            "failed": failed,
            "total_resources": total_resources,
            "total_duration_seconds": total_duration,
            "results": [
                {
                    "policy": r.policy_name,
                    "success": r.success,
                    "resources": r.resource_count,
                    "duration": r.duration_seconds,
                    "error": r.error,
                }
                for r in self.results
            ],
        }
