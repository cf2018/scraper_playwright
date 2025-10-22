# CloudWatch Alarms and Monitoring

# Lambda Function Error Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_error_rate" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-lambda-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors lambda error rate"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    FunctionName = aws_lambda_function.business_scraper.function_name
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-lambda-error-alarm"
  })
}

# Lambda Function Duration Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-lambda-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "240000" # 4 minutes (240 seconds in milliseconds)
  alarm_description   = "This metric monitors lambda duration"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    FunctionName = aws_lambda_function.business_scraper.function_name
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-lambda-duration-alarm"
  })
}

# Lambda Function Throttles Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-lambda-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors lambda throttles"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    FunctionName = aws_lambda_function.business_scraper.function_name
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-lambda-throttles-alarm"
  })
}

# API Gateway 4XX Error Alarm
resource "aws_cloudwatch_metric_alarm" "api_gateway_4xx_errors" {
  count               = var.enable_api_gateway && var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-api-4xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors API Gateway 4XX errors"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    ApiName   = aws_api_gateway_rest_api.business_scraper[0].name
    Stage     = var.api_gateway_stage_name
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-api-4xx-alarm"
  })
}

# API Gateway 5XX Error Alarm
resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx_errors" {
  count               = var.enable_api_gateway && var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-api-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors API Gateway 5XX errors"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    ApiName   = aws_api_gateway_rest_api.business_scraper[0].name
    Stage     = var.api_gateway_stage_name
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-api-5xx-alarm"
  })
}

# API Gateway Latency Alarm
resource "aws_cloudwatch_metric_alarm" "api_gateway_latency" {
  count               = var.enable_api_gateway && var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-api-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Average"
  threshold           = "10000" # 10 seconds in milliseconds
  alarm_description   = "This metric monitors API Gateway latency"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    ApiName   = aws_api_gateway_rest_api.business_scraper[0].name
    Stage     = var.api_gateway_stage_name
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-api-latency-alarm"
  })
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "business_scraper" {
  count          = var.enable_cloudwatch_dashboard ? 1 : 0
  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.business_scraper.function_name],
            [".", "Errors", ".", "."],
            [".", "Duration", ".", "."],
            [".", "Throttles", ".", "."]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Lambda Function Metrics"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = var.enable_api_gateway ? [
            ["AWS/ApiGateway", "Count", "ApiName", aws_api_gateway_rest_api.business_scraper[0].name, "Stage", var.api_gateway_stage_name],
            [".", "4XXError", ".", ".", ".", "."],
            [".", "5XXError", ".", ".", ".", "."],
            [".", "Latency", ".", ".", ".", "."]
          ] : []
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "API Gateway Metrics"
          view   = "timeSeries"
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 12
        width  = 24
        height = 6

        properties = {
          query   = "SOURCE '/aws/lambda/${aws_lambda_function.business_scraper.function_name}' | fields @timestamp, @message | sort @timestamp desc | limit 100"
          region  = var.aws_region
          title   = "Lambda Function Logs"
          view    = "table"
        }
      }
    ]
  })
}

# Custom CloudWatch Metric for business scraping success rate
resource "aws_cloudwatch_log_metric_filter" "scraping_success" {
  count          = var.enable_custom_metrics ? 1 : 0
  name           = "${var.project_name}-${var.environment}-scraping-success"
  log_group_name = aws_cloudwatch_log_group.lambda_logs[0].name
  pattern        = "[timestamp, request_id, level=\"INFO\", message=\"Scraping completed successfully\"]"

  metric_transformation {
    name      = "ScrapingSuccess"
    namespace = "BusinessScraper/${var.environment}"
    value     = "1"
  }
}

# Custom CloudWatch Metric for business scraping failures
resource "aws_cloudwatch_log_metric_filter" "scraping_failure" {
  count          = var.enable_custom_metrics ? 1 : 0
  name           = "${var.project_name}-${var.environment}-scraping-failure"
  log_group_name = aws_cloudwatch_log_group.lambda_logs[0].name
  pattern        = "[timestamp, request_id, level=\"ERROR\", message=\"Scraping failed\"]"

  metric_transformation {
    name      = "ScrapingFailure"
    namespace = "BusinessScraper/${var.environment}"
    value     = "1"
  }
}

# Alarm for custom scraping success rate
resource "aws_cloudwatch_metric_alarm" "scraping_success_rate" {
  count               = var.enable_custom_metrics && var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-scraping-success-rate"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  threshold           = "0.8" # 80% success rate threshold
  alarm_description   = "This metric monitors scraping success rate"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []
  treat_missing_data  = "breaching"

  metric_query {
    id = "success_rate"
    return_data = true
    metric {
      metric_name = "ScrapingSuccess"
      namespace   = "BusinessScraper/${var.environment}"
      period      = 900
      stat        = "Sum"
    }
  }

  metric_query {
    id = "failure_rate"
    return_data = false
    metric {
      metric_name = "ScrapingFailure"
      namespace   = "BusinessScraper/${var.environment}"
      period      = 900
      stat        = "Sum"
    }
  }

  metric_query {
    id          = "success_percentage"
    return_data = false
    expression  = "success_rate / (success_rate + failure_rate) * 100"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-success-rate-alarm"
  })
}