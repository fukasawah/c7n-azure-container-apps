# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
ポリシーローダーモジュール

Blob Storage またはローカルファイルから Cloud Custodian ポリシーを読み込みます。
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from c7n.policy import PolicyCollection

from c7n.config import Config
from c7n.policy import PolicyCollection as C7nPolicyCollection
from c7n import resources

log = logging.getLogger(__name__)


class PolicyLoader:
    """
    Cloud Custodian ポリシーローダー

    Blob Storage またはローカルファイルシステムからポリシーを読み込み、
    PolicyCollection オブジェクトを生成します。
    """

    def __init__(
        self,
        output_dir: str | None = None,
        log_group: str | None = None,
        metrics: str | None = None,
    ):
        """
        Args:
            output_dir: ポリシー実行結果の出力先
            log_group: Log Analytics ワークスペース
            metrics: メトリクス送信先
        """
        self.output_dir = output_dir or tempfile.mkdtemp()
        self.log_group = log_group
        self.metrics = metrics

        # c7n リソースの読み込み
        resources.load_available()

    def _build_options(self) -> Config:
        """c7n Config オブジェクトを構築"""
        # Azure プロバイダーを初期化
        from c7n_azure.provider import Azure

        config = Config.empty(
            **{
                "log_group": self.log_group,
                "metrics": self.metrics,
                "output_dir": self.output_dir,
            }
        )
        return Azure().initialize(config)

    def load_from_file(self, policy_path: str | Path) -> PolicyCollection:
        """
        ローカルファイルからポリシーを読み込む

        Args:
            policy_path: ポリシー YAML ファイルのパス

        Returns:
            PolicyCollection オブジェクト
        """
        policy_path = Path(policy_path)

        if not policy_path.exists():
            raise FileNotFoundError(f"Policy file not found: {policy_path}")

        log.info(f"Loading policy from file: {policy_path}")

        with open(policy_path) as f:
            policy_data = yaml.safe_load(f)

        options = self._build_options()
        policies = C7nPolicyCollection.from_data(policy_data, options)

        log.info(f"Loaded {len(policies)} policies")
        return policies

    def load_from_blob(
        self,
        blob_uri: str,
        session=None,
    ) -> PolicyCollection:
        """
        Azure Blob Storage からポリシーを読み込む

        Args:
            blob_uri: Blob Storage URI (例: https://account.blob.core.windows.net/container)
            session: c7n_azure Session オブジェクト（オプション）

        Returns:
            PolicyCollection オブジェクト
        """
        from c7n_azure.session import Session
        from c7n_azure.storage_utils import StorageUtilities as Storage
        from c7n.utils import local_session

        log.info(f"Loading policies from blob: {blob_uri}")

        s = session or local_session(Session)
        blob_client = Storage.get_blob_client_by_uri(blob_uri, s)
        (client, container, prefix) = blob_client

        # YAML ファイルを列挙
        blobs = [
            b for b in client.list_blobs(container, name_starts_with=prefix)
            if b.name.lower().endswith((".yml", ".yaml"))
        ]

        if not blobs:
            log.warning(f"No policy files found in {blob_uri}")
            return C7nPolicyCollection([], self._build_options())

        # すべてのポリシーを読み込み
        all_policies = []
        options = self._build_options()

        for blob in blobs:
            try:
                log.info(f"Loading policy: {blob.name}")
                blob_data = client.get_blob_to_bytes(container, blob.name)
                policy_data = yaml.safe_load(blob_data.content)

                policies = C7nPolicyCollection.from_data(policy_data, options)
                for p in policies:
                    p.validate()
                    all_policies.append(p)
                    log.info(f"  Loaded policy: {p.name}")

            except Exception as e:
                log.error(f"Failed to load policy {blob.name}: {e}")
                continue

        log.info(f"Total loaded: {len(all_policies)} policies")
        return C7nPolicyCollection(all_policies, options)

    def load_from_string(self, yaml_content: str) -> PolicyCollection:
        """
        YAML 文字列からポリシーを読み込む

        Args:
            yaml_content: ポリシー定義の YAML 文字列

        Returns:
            PolicyCollection オブジェクト
        """
        policy_data = yaml.safe_load(yaml_content)
        options = self._build_options()
        return C7nPolicyCollection.from_data(policy_data, options)
