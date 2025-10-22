# Input Variables for Business Scraper Infrastructure

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "business-scraper"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "business-scraper"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
  
  validation {
    condition     = var.lambda_timeout >= 1 && var.lambda_timeout <= 900
    error_message = "Lambda timeout must be between 1 and 900 seconds."
  }
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 1024
  
  validation {
    condition     = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240
    error_message = "Lambda memory size must be between 128 and 10240 MB."
  }
}

variable "lambda_ephemeral_storage" {
  description = "Lambda function ephemeral storage in MB"
  type        = number
  default     = 512
  
  validation {
    condition     = var.lambda_ephemeral_storage >= 512 && var.lambda_ephemeral_storage <= 10240
    error_message = "Lambda ephemeral storage must be between 512 and 10240 MB."
  }
}

variable "mongodb_connection_string" {
  description = "MongoDB connection string (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "mongodb_database" {
  description = "MongoDB database name"
  type        = string
  default     = "business_scraper"
}

variable "enable_api_gateway" {
  description = "Enable API Gateway for HTTP endpoints"
  type        = bool
  default     = true
}

variable "api_gateway_stage_name" {
  description = "API Gateway stage name"
  type        = string
  default     = "prod"
  validation {
    condition     = can(regex("^[a-zA-Z0-9_-]+$", var.api_gateway_stage_name))
    error_message = "API Gateway stage name must contain only alphanumeric characters, hyphens, and underscores."
  }
}

variable "enable_cloudwatch_logs" {
  description = "Enable CloudWatch logging for Lambda"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 14
  
  validation {
    condition = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch retention period."
  }
}

variable "enable_xray_tracing" {
  description = "Enable AWS X-Ray tracing for Lambda"
  type        = bool
  default     = false
}

variable "ecr_repository_name" {
  description = "ECR repository name for Lambda container image"
  type        = string
  default     = "business-scraper"
}

variable "container_image_tag" {
  description = "Container image tag to deploy"
  type        = string
  default     = "latest"
}

variable "enable_vpc" {
  description = "Deploy Lambda in VPC for database access"
  type        = bool
  default     = false
}

variable "vpc_subnet_ids" {
  description = "VPC subnet IDs for Lambda (required if enable_vpc is true)"
  type        = list(string)
  default     = []
}

variable "vpc_security_group_ids" {
  description = "VPC security group IDs for Lambda (required if enable_vpc is true)"
  type        = list(string)
  default     = []
}

variable "enable_scheduled_execution" {
  description = "Enable scheduled execution via EventBridge"
  type        = bool
  default     = false
}

variable "schedule_expression" {
  description = "EventBridge schedule expression (e.g., 'rate(1 hour)' or 'cron(0 9 * * ? *)')"
  type        = string
  default     = "rate(1 day)"
}

variable "default_search_query" {
  description = "Default search query for scheduled executions"
  type        = string
  default     = "registro de marcas en buenos aires"
}

variable "default_max_results" {
  description = "Default maximum results for scheduled executions"
  type        = number
  default     = 50
}

variable "enable_cloudwatch_alarms" {
  description = "Whether to create CloudWatch alarms"
  type        = bool
  default     = true
}

variable "enable_cloudwatch_dashboard" {
  description = "Whether to create CloudWatch dashboard"
  type        = bool
  default     = true
}

variable "enable_custom_metrics" {
  description = "Whether to create custom CloudWatch metrics"
  type        = bool
  default     = true
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}