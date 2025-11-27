# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
config モジュールのテスト
"""

import os
from unittest import mock

import pytest

from c7n_azure_runner.config import OutputConfig, RunnerConfig, StorageConfig


class TestStorageConfig:
    """StorageConfig のテスト"""

    def test_default_values(self):
        """デフォルト値のテスト"""
        config = StorageConfig()
        assert config.policy_uri == ""
        assert config.queue_storage_account == ""
        assert config.queue_name == ""

    def test_custom_values(self):
        """カスタム値のテスト"""
        config = StorageConfig(
            policy_uri="https://example.blob.core.windows.net/policies",
            queue_storage_account="myaccount",
            queue_name="myqueue",
        )
        assert config.policy_uri == "https://example.blob.core.windows.net/policies"
        assert config.queue_storage_account == "myaccount"
        assert config.queue_name == "myqueue"


class TestOutputConfig:
    """OutputConfig のテスト"""

    def test_default_values(self):
        """デフォルト値のテスト"""
        config = OutputConfig()
        assert config.output_dir == "/tmp/c7n-output"
        assert config.log_group == ""
        assert config.metrics_target == ""


class TestRunnerConfig:
    """RunnerConfig のテスト"""

    def test_default_values(self):
        """デフォルト値のテスト"""
        config = RunnerConfig()
        assert config.subscription_id == ""
        assert config.execution_mode == "single"
        assert isinstance(config.storage, StorageConfig)
        assert isinstance(config.output, OutputConfig)

    def test_from_env(self):
        """環境変数からの読み込みテスト"""
        env_vars = {
            "AZURE_SUBSCRIPTION_ID": "test-subscription-id",
            "AZURE_POLICY_STORAGE_URI": "https://test.blob.core.windows.net/policies",
            "AZURE_QUEUE_STORAGE_ACCOUNT": "teststorage",
            "AZURE_QUEUE_NAME": "testqueue",
            "AZURE_OUTPUT_DIR": "/custom/output",
            "AZURE_LOG_GROUP": "testloggroup",
            "AZURE_METRICS_TARGET": "testmetrics",
            "C7N_POLICY_FILE": "/path/to/policy.yml",
            "C7N_EVENT_DATA": '{"test": "data"}',
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            config = RunnerConfig.from_env()

        assert config.subscription_id == "test-subscription-id"
        assert config.storage.policy_uri == "https://test.blob.core.windows.net/policies"
        assert config.storage.queue_storage_account == "teststorage"
        assert config.storage.queue_name == "testqueue"
        assert config.output.output_dir == "/custom/output"
        assert config.output.log_group == "testloggroup"
        assert config.output.metrics_target == "testmetrics"
        assert config.policy_file == "/path/to/policy.yml"
        assert config.event_data == '{"test": "data"}'

    def test_from_env_with_defaults(self):
        """環境変数が未設定の場合のデフォルト値テスト"""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = RunnerConfig.from_env()

        assert config.subscription_id == ""
        assert config.storage.policy_uri == ""
        assert config.output.output_dir == "/tmp/c7n-output"

    def test_validate_for_event_mode(self):
        """イベントモードのバリデーションテスト"""
        # 必須項目が欠けている場合
        config = RunnerConfig()
        errors = config.validate_for_event_mode()
        assert len(errors) == 4
        assert "AZURE_SUBSCRIPTION_ID is required" in errors
        assert "AZURE_QUEUE_STORAGE_ACCOUNT is required for event mode" in errors
        assert "AZURE_QUEUE_NAME is required for event mode" in errors
        assert "AZURE_POLICY_STORAGE_URI is required" in errors

        # 必須項目がすべて設定されている場合
        config = RunnerConfig(
            subscription_id="test-sub",
            storage=StorageConfig(
                policy_uri="https://test.blob.core.windows.net/policies",
                queue_storage_account="teststorage",
                queue_name="testqueue",
            ),
        )
        errors = config.validate_for_event_mode()
        assert len(errors) == 0

    def test_validate_for_scheduled_mode(self):
        """定期実行モードのバリデーションテスト"""
        # 必須項目が欠けている場合
        config = RunnerConfig()
        errors = config.validate_for_scheduled_mode()
        assert len(errors) == 2

        # 必須項目がすべて設定されている場合
        config = RunnerConfig(
            subscription_id="test-sub",
            storage=StorageConfig(
                policy_uri="https://test.blob.core.windows.net/policies",
            ),
        )
        errors = config.validate_for_scheduled_mode()
        assert len(errors) == 0

    def test_validate_for_single_mode(self):
        """単一実行モードのバリデーションテスト"""
        # 必須項目が欠けている場合
        config = RunnerConfig()
        errors = config.validate_for_single_mode()
        assert len(errors) == 2

        # policy_file が設定されている場合
        config = RunnerConfig(
            subscription_id="test-sub",
            policy_file="/path/to/policy.yml",
        )
        errors = config.validate_for_single_mode()
        assert len(errors) == 0

        # policy_uri が設定されている場合
        config = RunnerConfig(
            subscription_id="test-sub",
            storage=StorageConfig(
                policy_uri="https://test.blob.core.windows.net/policies",
            ),
        )
        errors = config.validate_for_single_mode()
        assert len(errors) == 0
