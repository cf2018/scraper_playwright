# Output values for Business Scraper Infrastructure

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.business_scraper.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.business_scraper.function_name
}

output "lambda_function_url" {
  description = "Lambda function URL (if enabled)"
  value       = var.enable_api_gateway ? null : try(aws_lambda_function_url.business_scraper[0].function_url, null)
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.business_scraper.repository_url
}

output "ecr_repository_name" {
  description = "ECR repository name"
  value       = aws_ecr_repository.business_scraper.name
}

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = var.enable_api_gateway ? aws_api_gateway_deployment.business_scraper[0].invoke_url : null
}

output "api_gateway_stage_url" {
  description = "API Gateway stage URL"
  value       = var.enable_api_gateway ? "${aws_api_gateway_deployment.business_scraper[0].invoke_url}${var.api_gateway_stage_name}" : null
}

output "cloudwatch_log_group_name" {
  description = "CloudWatch log group name"
  value       = var.enable_cloudwatch_logs ? aws_cloudwatch_log_group.lambda_logs[0].name : null
}

output "iam_role_arn" {
  description = "IAM role ARN for Lambda function"
  value       = aws_iam_role.lambda_role.arn
}

output "lambda_security_group_id" {
  description = "Security group ID for Lambda (if VPC enabled)"
  value       = var.enable_vpc ? aws_security_group.lambda_sg[0].id : null
}

output "eventbridge_rule_name" {
  description = "EventBridge rule name (if scheduled execution enabled)"
  value       = var.enable_scheduled_execution ? aws_cloudwatch_event_rule.lambda_schedule[0].name : null
}

# API Gateway endpoints
output "api_endpoints" {
  description = "Available API endpoints"
  value = var.enable_api_gateway ? {
    scrape_endpoint = "${aws_api_gateway_deployment.business_scraper[0].invoke_url}${var.api_gateway_stage_name}/scrape"
    health_endpoint = "${aws_api_gateway_deployment.business_scraper[0].invoke_url}${var.api_gateway_stage_name}/health"
    base_url       = "${aws_api_gateway_deployment.business_scraper[0].invoke_url}${var.api_gateway_stage_name}"
  } : null
}

# Environment configuration
output "environment_config" {
  description = "Environment configuration summary"
  value = {
    environment     = var.environment
    aws_region      = var.aws_region
    lambda_timeout  = var.lambda_timeout
    lambda_memory   = var.lambda_memory_size
    vpc_enabled     = var.enable_vpc
    api_enabled     = var.enable_api_gateway
    logs_enabled    = var.enable_cloudwatch_logs
    xray_enabled    = var.enable_xray_tracing
    schedule_enabled = var.enable_scheduled_execution
  }
}

# Deployment information
output "deployment_info" {
  description = "Deployment information"
  value = {
    container_image    = "${aws_ecr_repository.business_scraper.repository_url}:${var.container_image_tag}"
    lambda_function    = aws_lambda_function.business_scraper.function_name
    last_modified     = aws_lambda_function.business_scraper.last_modified
    runtime           = aws_lambda_function.business_scraper.package_type
  }
}