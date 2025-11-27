# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
CLI エントリポイント

Cloud Custodian Azure Container Apps のコマンドラインインターフェース
"""

from __future__ import annotations

import json
import logging
import sys

import click

from c7n_azure_runner.config import RunnerConfig
from c7n_azure_runner.event_processor import EventProcessor
from c7n_azure_runner.policy_executor import PolicyExecutor
from c7n_azure_runner.policy_loader import PolicyLoader

# c7n_azure の初期化
from c7n_azure import entry

entry.initialize_azure()

log = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """ロギングの設定"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="詳細なログ出力を有効化")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """Cloud Custodian Azure Container Apps Runner"""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@main.command("run-policy")
@click.option(
    "--policy-file", "-p",
    envvar="C7N_POLICY_FILE",
    help="ポリシー YAML ファイルのパス",
)
@click.option(
    "--policy-uri",
    envvar="AZURE_POLICY_STORAGE_URI",
    help="ポリシーが格納された Blob Storage URI",
)
@click.option(
    "--output-dir", "-o",
    envvar="AZURE_OUTPUT_DIR",
    default="/tmp/c7n-output",
    help="出力ディレクトリ",
)
@click.option(
    "--subscription-id", "-s",
    envvar="AZURE_SUBSCRIPTION_ID",
    help="Azure サブスクリプション ID",
)
@click.pass_context
def run_policy(
    ctx: click.Context,
    policy_file: str | None,
    policy_uri: str | None,
    output_dir: str,
    subscription_id: str | None,
) -> None:
    """
    単一ポリシーまたは Blob Storage 内のポリシーを実行

    ローカルファイルまたは Blob Storage からポリシーを読み込み実行します。
    """
    if not policy_file and not policy_uri:
        raise click.UsageError("--policy-file または --policy-uri を指定してください")

    if subscription_id:
        import os
        os.environ["AZURE_SUBSCRIPTION_ID"] = subscription_id

    loader = PolicyLoader(output_dir=output_dir)
    executor = PolicyExecutor()

    try:
        if policy_file:
            policies = loader.load_from_file(policy_file)
        else:
            policies = loader.load_from_blob(policy_uri)

        if not policies:
            log.warning("No policies loaded")
            sys.exit(0)

        results = executor.execute_policies(policies)
        summary = executor.get_summary()

        click.echo(json.dumps(summary, indent=2, default=str))

        if summary["failed"] > 0:
            sys.exit(1)

    except Exception as e:
        log.exception(f"Policy execution failed: {e}")
        sys.exit(1)


@main.command("run-event")
@click.option(
    "--event-data",
    envvar="C7N_EVENT_DATA",
    help="イベントデータ（JSON 文字列）",
)
@click.option(
    "--queue-storage-account",
    envvar="AZURE_QUEUE_STORAGE_ACCOUNT",
    help="Storage Queue のストレージアカウント名",
)
@click.option(
    "--queue-name",
    envvar="AZURE_QUEUE_NAME",
    help="Storage Queue 名",
)
@click.option(
    "--policy-uri",
    envvar="AZURE_POLICY_STORAGE_URI",
    required=True,
    help="ポリシーが格納された Blob Storage URI",
)
@click.option(
    "--output-dir", "-o",
    envvar="AZURE_OUTPUT_DIR",
    default="/tmp/c7n-output",
    help="出力ディレクトリ",
)
@click.option(
    "--subscription-id", "-s",
    envvar="AZURE_SUBSCRIPTION_ID",
    help="Azure サブスクリプション ID",
)
@click.pass_context
def run_event(
    ctx: click.Context,
    event_data: str | None,
    queue_storage_account: str | None,
    queue_name: str | None,
    policy_uri: str,
    output_dir: str,
    subscription_id: str | None,
) -> None:
    """
    イベント駆動でポリシーを実行

    Storage Queue からイベントを取得するか、直接イベントデータを渡して
    該当するポリシーを実行します。
    """
    if subscription_id:
        import os
        os.environ["AZURE_SUBSCRIPTION_ID"] = subscription_id

    loader = PolicyLoader(output_dir=output_dir)
    executor = PolicyExecutor()
    event_processor = EventProcessor()

    try:
        # ポリシーを読み込み
        policies = loader.load_from_blob(policy_uri)
        if not policies:
            log.warning("No policies loaded")
            sys.exit(0)

        # イベントデータを取得
        if event_data:
            # 直接渡されたイベントデータを使用
            event_dict = json.loads(event_data)
        elif queue_storage_account and queue_name:
            # Storage Queue からイベントを取得
            from c7n_azure_container_apps.queue_handler import QueueHandler

            handler = QueueHandler(queue_storage_account, queue_name)
            event_dict = handler.process_single_message()

            if event_dict is None:
                log.info("No messages in queue")
                sys.exit(0)
        else:
            raise click.UsageError(
                "--event-data または --queue-storage-account と --queue-name を指定してください"
            )

        # イベントをパース
        parsed_event = event_processor.parse_event(event_dict)
        log.info(f"Processing event: {parsed_event.event_id}, operation: {parsed_event.operation_name}")

        # マッチするポリシーを検索
        matching_policies = event_processor.find_matching_policies(parsed_event, policies)

        if not matching_policies:
            log.info(f"No policies match event operation: {parsed_event.operation_name}")
            sys.exit(0)

        # マッチしたポリシーを実行
        for policy in matching_policies:
            executor.execute_policy(policy, event=parsed_event.raw_data)

        summary = executor.get_summary()
        click.echo(json.dumps(summary, indent=2, default=str))

        if summary["failed"] > 0:
            sys.exit(1)

    except Exception as e:
        log.exception(f"Event processing failed: {e}")
        sys.exit(1)


@main.command("run-scheduled")
@click.option(
    "--policy-uri",
    envvar="AZURE_POLICY_STORAGE_URI",
    required=True,
    help="ポリシーが格納された Blob Storage URI",
)
@click.option(
    "--output-dir", "-o",
    envvar="AZURE_OUTPUT_DIR",
    default="/tmp/c7n-output",
    help="出力ディレクトリ",
)
@click.option(
    "--subscription-id", "-s",
    envvar="AZURE_SUBSCRIPTION_ID",
    help="Azure サブスクリプション ID",
)
@click.option(
    "--mode-filter",
    default="container-periodic",
    help="実行するポリシーのモードタイプでフィルタ",
)
@click.pass_context
def run_scheduled(
    ctx: click.Context,
    policy_uri: str,
    output_dir: str,
    subscription_id: str | None,
    mode_filter: str,
) -> None:
    """
    定期実行用にポリシーを実行

    指定されたモードタイプのポリシーのみを実行します。
    """
    if subscription_id:
        import os
        os.environ["AZURE_SUBSCRIPTION_ID"] = subscription_id

    loader = PolicyLoader(output_dir=output_dir)
    executor = PolicyExecutor()

    try:
        # ポリシーを読み込み
        all_policies = loader.load_from_blob(policy_uri)
        if not all_policies:
            log.warning("No policies loaded")
            sys.exit(0)

        # モードでフィルタ
        filtered_policies = [
            p for p in all_policies
            if p.data.get("mode", {}).get("type") == mode_filter
        ]

        if not filtered_policies:
            log.info(f"No policies with mode '{mode_filter}' found")
            sys.exit(0)

        log.info(f"Found {len(filtered_policies)} policies with mode '{mode_filter}'")

        # ポリシーを実行
        from c7n.policy import PolicyCollection as C7nPolicyCollection
        policy_collection = C7nPolicyCollection(filtered_policies, all_policies.options)
        results = executor.execute_policies(policy_collection)

        summary = executor.get_summary()
        click.echo(json.dumps(summary, indent=2, default=str))

        if summary["failed"] > 0:
            sys.exit(1)

    except Exception as e:
        log.exception(f"Scheduled execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
