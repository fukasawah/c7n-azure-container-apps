# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
設定管理モジュール

環境変数からの設定読み込みと検証を行います。
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field


class StorageConfig(BaseModel):
    """Blob Storage 設定"""

    policy_uri: str = Field(
        default="",
        description="ポリシーファイルが格納された Blob Storage URI",
    )
    queue_storage_account: str = Field(
        default="",
        description="イベントキュー用ストレージアカウント名",
    )
    queue_name: str = Field(
        default="",
        description="イベントキュー名",
    )


class OutputConfig(BaseModel):
    """出力設定"""

    output_dir: str = Field(
        default="/tmp/c7n-output",
        description="ポリシー実行結果の出力先ディレクトリ",
    )
    log_group: str = Field(
        default="",
        description="Log Analytics ワークスペース名",
    )
    metrics_target: str = Field(
        default="",
        description="メトリクス送信先",
    )


class RunnerConfig(BaseModel):
    """
    Cloud Custodian Azure Runner の設定

    環境変数または直接の値から設定を読み込みます。
    """

    subscription_id: str = Field(
        default="",
        description="Azure サブスクリプション ID",
    )
    storage: StorageConfig = Field(default_factory=StorageConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    policy_file: str = Field(
        default="",
        description="単一ポリシー実行時のポリシーファイルパス",
    )
    event_data: str = Field(
        default="",
        description="イベントデータ（JSON文字列）",
    )
    execution_mode: Literal["scheduled", "event", "single"] = Field(
        default="single",
        description="実行モード",
    )

    @classmethod
    def from_env(cls) -> RunnerConfig:
        """環境変数から設定を読み込む"""
        storage = StorageConfig(
            policy_uri=os.environ.get("AZURE_POLICY_STORAGE_URI", ""),
            queue_storage_account=os.environ.get("AZURE_QUEUE_STORAGE_ACCOUNT", ""),
            queue_name=os.environ.get("AZURE_QUEUE_NAME", ""),
        )

        output = OutputConfig(
            output_dir=os.environ.get("AZURE_OUTPUT_DIR", "/tmp/c7n-output"),
            log_group=os.environ.get("AZURE_LOG_GROUP", ""),
            metrics_target=os.environ.get("AZURE_METRICS_TARGET", ""),
        )

        return cls(
            subscription_id=os.environ.get("AZURE_SUBSCRIPTION_ID", ""),
            storage=storage,
            output=output,
            policy_file=os.environ.get("C7N_POLICY_FILE", ""),
            event_data=os.environ.get("C7N_EVENT_DATA", ""),
        )

    def validate_for_event_mode(self) -> list[str]:
        """イベントモード用のバリデーション"""
        errors = []
        if not self.subscription_id:
            errors.append("AZURE_SUBSCRIPTION_ID is required")
        if not self.storage.queue_storage_account:
            errors.append("AZURE_QUEUE_STORAGE_ACCOUNT is required for event mode")
        if not self.storage.queue_name:
            errors.append("AZURE_QUEUE_NAME is required for event mode")
        if not self.storage.policy_uri:
            errors.append("AZURE_POLICY_STORAGE_URI is required")
        return errors

    def validate_for_scheduled_mode(self) -> list[str]:
        """定期実行モード用のバリデーション"""
        errors = []
        if not self.subscription_id:
            errors.append("AZURE_SUBSCRIPTION_ID is required")
        if not self.storage.policy_uri:
            errors.append("AZURE_POLICY_STORAGE_URI is required")
        return errors

    def validate_for_single_mode(self) -> list[str]:
        """単一実行モード用のバリデーション"""
        errors = []
        if not self.subscription_id:
            errors.append("AZURE_SUBSCRIPTION_ID is required")
        if not self.policy_file and not self.storage.policy_uri:
            errors.append("Either C7N_POLICY_FILE or AZURE_POLICY_STORAGE_URI is required")
        return errors
