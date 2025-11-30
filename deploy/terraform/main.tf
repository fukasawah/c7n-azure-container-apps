# Azure Container Apps Job - Cloud Custodian Runner
# Terraform サンプル構成

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.85"
    }
  }
}

provider "azurerm" {
  features {}
}

# =============================================================================
# Variables
# =============================================================================

variable "resource_group_name" {
  description = "リソースグループ名"
  type        = string
  default     = "rg-c7n-container-apps"
}

variable "location" {
  description = "Azureリージョン"
  type        = string
  default     = "japaneast"
}

variable "environment_name" {
  description = "Container Apps 環境名"
  type        = string
  default     = "cae-c7n"
}

variable "subscription_id" {
  description = "監視対象の Azure サブスクリプション ID"
  type        = string
}

variable "schedule_cron" {
  description = "定期実行のCron式"
  type        = string
  default     = "0 */6 * * *" # 6時間ごと
}

variable "tags" {
  description = "リソースに付与するタグ"
  type        = map(string)
  default = {
    Environment = "production"
    Project     = "cloud-custodian"
    ManagedBy   = "terraform"
  }
}

# =============================================================================
# Resource Group
# =============================================================================

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# =============================================================================
# Log Analytics Workspace
# =============================================================================

resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-c7n-${var.location}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

# =============================================================================
# Storage Account (ポリシー格納 & イベントキュー用)
# =============================================================================

resource "azurerm_storage_account" "main" {
  name                     = "stc7n${substr(md5(azurerm_resource_group.main.id), 0, 8)}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    versioning_enabled = true
  }

  tags = var.tags
}

resource "azurerm_storage_container" "policies" {
  name                  = "policies"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_queue" "events" {
  name                 = "c7n-events"
  storage_account_name = azurerm_storage_account.main.name
}

# =============================================================================
# User Assigned Managed Identity
# =============================================================================

resource "azurerm_user_assigned_identity" "c7n" {
  name                = "id-c7n-runner"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = var.tags
}

# Storage Blob Data Reader role for policy files
resource "azurerm_role_assignment" "blob_reader" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_user_assigned_identity.c7n.principal_id
}

# Storage Queue Data Contributor role for event queue
resource "azurerm_role_assignment" "queue_contributor" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_user_assigned_identity.c7n.principal_id
}

# Reader role at subscription level for resource enumeration
resource "azurerm_role_assignment" "subscription_reader" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.c7n.principal_id
}

# =============================================================================
# Container Apps Environment
# =============================================================================

resource "azurerm_container_app_environment" "main" {
  name                       = var.environment_name
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = var.tags
}

# =============================================================================
# Container Apps Job - Scheduled
# =============================================================================

resource "azurerm_container_app_job" "scheduled" {
  name                         = "caj-c7n-scheduled"
  location                     = azurerm_resource_group.main.location
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id

  replica_timeout_in_seconds = 1800
  replica_retry_limit        = 1

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.c7n.id]
  }

  schedule_trigger_config {
    cron_expression          = var.schedule_cron
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name   = "c7n-runner"
      image  = "ghcr.io/fukasawah/c7n-azure-container-apps:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AZURE_SUBSCRIPTION_ID"
        value = var.subscription_id
      }

      env {
        name  = "AZURE_POLICY_STORAGE_URI"
        value = "https://${azurerm_storage_account.main.name}.blob.core.windows.net/${azurerm_storage_container.policies.name}"
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.c7n.client_id
      }

      env {
        name  = "C7N_EXECUTION_MODE"
        value = "scheduled"
      }
    }
  }

  tags = var.tags
}

# =============================================================================
# Container Apps Job - Event Driven
# =============================================================================

resource "azurerm_container_app_job" "event" {
  name                         = "caj-c7n-event"
  location                     = azurerm_resource_group.main.location
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id

  replica_timeout_in_seconds = 1800
  replica_retry_limit        = 1

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.c7n.id]
  }

  event_trigger_config {
    parallelism              = 1
    replica_completion_count = 1

    scale {
      min_executions              = 0
      max_executions              = 10
      polling_interval_in_seconds = 60

      rules {
        name = "azure-queue"
        type = "azure-queue"

        metadata = {
          accountName = azurerm_storage_account.main.name
          queueName   = azurerm_storage_queue.events.name
          queueLength = "1"
        }

        authentication {
          secret_name       = "queue-connection"
          trigger_parameter = "connection"
        }
      }
    }
  }

  secret {
    name  = "queue-connection"
    value = azurerm_storage_account.main.primary_connection_string
  }

  template {
    container {
      name   = "c7n-runner"
      image  = "ghcr.io/fukasawah/c7n-azure-container-apps:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AZURE_SUBSCRIPTION_ID"
        value = var.subscription_id
      }

      env {
        name  = "AZURE_POLICY_STORAGE_URI"
        value = "https://${azurerm_storage_account.main.name}.blob.core.windows.net/${azurerm_storage_container.policies.name}"
      }

      env {
        name  = "AZURE_QUEUE_STORAGE_ACCOUNT"
        value = azurerm_storage_account.main.name
      }

      env {
        name  = "AZURE_QUEUE_NAME"
        value = azurerm_storage_queue.events.name
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.c7n.client_id
      }

      env {
        name  = "C7N_EXECUTION_MODE"
        value = "event"
      }
    }
  }

  tags = var.tags
}

# =============================================================================
# Event Grid Subscription (Azure リソースイベントを Storage Queue に転送)
# =============================================================================

resource "azurerm_eventgrid_event_subscription" "resource_events" {
  name  = "c7n-resource-events"
  scope = "/subscriptions/${var.subscription_id}"

  storage_queue_endpoint {
    storage_account_id = azurerm_storage_account.main.id
    queue_name         = azurerm_storage_queue.events.name
  }

  included_event_types = [
    "Microsoft.Resources.ResourceWriteSuccess"
  ]

  retry_policy {
    max_delivery_attempts = 30
    event_time_to_live    = 1440 # 24 hours
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "resource_group_name" {
  description = "リソースグループ名"
  value       = azurerm_resource_group.main.name
}

output "storage_account_name" {
  description = "ストレージアカウント名"
  value       = azurerm_storage_account.main.name
}

output "policy_container_url" {
  description = "ポリシー格納用 Blob Container の URL"
  value       = "https://${azurerm_storage_account.main.name}.blob.core.windows.net/${azurerm_storage_container.policies.name}"
}

output "managed_identity_client_id" {
  description = "Managed Identity のクライアント ID"
  value       = azurerm_user_assigned_identity.c7n.client_id
}

output "scheduled_job_name" {
  description = "定期実行ジョブ名"
  value       = azurerm_container_app_job.scheduled.name
}

output "event_job_name" {
  description = "イベント駆動ジョブ名"
  value       = azurerm_container_app_job.event.name
}
