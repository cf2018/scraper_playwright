# API Gateway for Business Scraper Lambda

resource "aws_api_gateway_rest_api" "business_scraper" {
  count       = var.enable_api_gateway ? 1 : 0
  name        = "${var.project_name}-${var.environment}-api"
  description = "API Gateway for Business Scraper Lambda function"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-api"
  })
}

# Root resource - proxy all requests to Lambda
resource "aws_api_gateway_resource" "proxy" {
  count       = var.enable_api_gateway ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.business_scraper[0].id
  parent_id   = aws_api_gateway_rest_api.business_scraper[0].root_resource_id
  path_part   = "{proxy+}"
}

# ANY method for proxy resource
resource "aws_api_gateway_method" "proxy" {
  count         = var.enable_api_gateway ? 1 : 0
  rest_api_id   = aws_api_gateway_rest_api.business_scraper[0].id
  resource_id   = aws_api_gateway_resource.proxy[0].id
  http_method   = "ANY"
  authorization = "NONE"
}

# Integration with Lambda
resource "aws_api_gateway_integration" "lambda_proxy" {
  count       = var.enable_api_gateway ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.business_scraper[0].id
  resource_id = aws_api_gateway_method.proxy[0].resource_id
  http_method = aws_api_gateway_method.proxy[0].http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.business_scraper.invoke_arn
}

# Root method (for requests to the root path)
resource "aws_api_gateway_method" "proxy_root" {
  count         = var.enable_api_gateway ? 1 : 0
  rest_api_id   = aws_api_gateway_rest_api.business_scraper[0].id
  resource_id   = aws_api_gateway_rest_api.business_scraper[0].root_resource_id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_root" {
  count       = var.enable_api_gateway ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.business_scraper[0].id
  resource_id = aws_api_gateway_method.proxy_root[0].resource_id
  http_method = aws_api_gateway_method.proxy_root[0].http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.business_scraper.invoke_arn
}

# API Gateway deployment
resource "aws_api_gateway_deployment" "business_scraper" {
  count       = var.enable_api_gateway ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.business_scraper[0].id
  stage_name  = var.api_gateway_stage_name

  depends_on = [
    aws_api_gateway_method.proxy,
    aws_api_gateway_integration.lambda_proxy,
    aws_api_gateway_method.proxy_root,
    aws_api_gateway_integration.lambda_root,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  count         = var.enable_api_gateway ? 1 : 0
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.business_scraper.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.business_scraper[0].execution_arn}/*/*"
}

# API Gateway Stage (for more control over deployment)
resource "aws_api_gateway_stage" "business_scraper" {
  count         = var.enable_api_gateway ? 1 : 0
  deployment_id = aws_api_gateway_deployment.business_scraper[0].id
  rest_api_id   = aws_api_gateway_rest_api.business_scraper[0].id
  stage_name    = var.api_gateway_stage_name

  # Enable CloudWatch logging for API Gateway
  dynamic "access_log_settings" {
    for_each = var.enable_cloudwatch_logs ? [1] : []
    content {
      destination_arn = aws_cloudwatch_log_group.api_gateway_logs[0].arn
      format = jsonencode({
        requestId      = "$context.requestId"
        ip            = "$context.identity.sourceIp"
        caller        = "$context.identity.caller"
        user          = "$context.identity.user"
        requestTime   = "$context.requestTime"
        httpMethod    = "$context.httpMethod"
        resourcePath  = "$context.resourcePath"
        status        = "$context.status"
        protocol      = "$context.protocol"
        responseLength = "$context.responseLength"
        responseTime   = "$context.responseTime"
        error         = "$context.error.message"
        integrationError = "$context.integration.error"
      })
    }
  }

  # Enable X-Ray tracing for API Gateway
  xray_tracing_enabled = var.enable_xray_tracing

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-api-stage"
  })
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  count             = var.enable_api_gateway && var.enable_cloudwatch_logs ? 1 : 0
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-api-logs"
  })
}

# API Gateway method settings for throttling and caching
resource "aws_api_gateway_method_settings" "business_scraper" {
  count       = var.enable_api_gateway ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.business_scraper[0].id
  stage_name  = aws_api_gateway_stage.business_scraper[0].stage_name
  method_path = "*/*"

  settings {
    # Enable CloudWatch metrics
    metrics_enabled = true
    logging_level   = var.enable_cloudwatch_logs ? "INFO" : "OFF"
    
    # Throttling settings
    throttling_rate_limit  = 100
    throttling_burst_limit = 200
    
    # Caching (disabled by default for dynamic content)
    caching_enabled = false
  }
}

# Usage Plan for API rate limiting
resource "aws_api_gateway_usage_plan" "business_scraper" {
  count       = var.enable_api_gateway ? 1 : 0
  name        = "${var.project_name}-${var.environment}-usage-plan"
  description = "Usage plan for Business Scraper API"

  api_stages {
    api_id = aws_api_gateway_rest_api.business_scraper[0].id
    stage  = aws_api_gateway_stage.business_scraper[0].stage_name
  }

  quota_settings {
    limit  = 1000
    period = "DAY"
  }

  throttle_settings {
    rate_limit  = 100
    burst_limit = 200
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-usage-plan"
  })
}