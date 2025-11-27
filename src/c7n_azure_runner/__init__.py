# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
c7n_azure_runner - Cloud Custodian Azure の共通コアライブラリ

トリガー非依存のポリシー読み込み・実行ロジックを提供します。
"""

__version__ = "0.1.0"

from c7n_azure_runner.config import RunnerConfig
from c7n_azure_runner.event_processor import EventProcessor
from c7n_azure_runner.policy_executor import PolicyExecutor
from c7n_azure_runner.policy_loader import PolicyLoader

__all__ = [
    "RunnerConfig",
    "PolicyLoader",
    "PolicyExecutor",
    "EventProcessor",
]
