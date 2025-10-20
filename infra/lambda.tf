# ECR Repository for Lambda Container Image

resource "aws_ecr_repository" "business_scraper" {
  name                 = "${var.project_name}-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ecr"
  })
}

resource "aws_ecr_lifecycle_policy" "business_scraper" {
  repository = aws_ecr_repository.business_scraper.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# IAM Role for Lambda Function
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-lambda-role"
  })
}

# Basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_role.name
}

# VPC execution policy (if VPC is enabled)
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  count      = var.enable_vpc ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
  role       = aws_iam_role.lambda_role.name
}

# X-Ray tracing policy (if X-Ray is enabled)
resource "aws_iam_role_policy_attachment" "lambda_xray_execution" {
  count      = var.enable_xray_tracing ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
  role       = aws_iam_role.lambda_role.name
}

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "lambda_logs" {
  count             = var.enable_cloudwatch_logs ? 1 : 0
  name              = "/aws/lambda/${var.lambda_function_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-logs"
  })
}

# Security Group for Lambda (if VPC is enabled)
resource "aws_security_group" "lambda_sg" {
  count       = var.enable_vpc ? 1 : 0
  name        = "${var.project_name}-${var.environment}-lambda-sg"
  description = "Security group for Business Scraper Lambda function"

  # Allow all outbound traffic (for web scraping)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow HTTPS outbound (specific for web scraping)
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS outbound for web scraping"
  }

  # Allow HTTP outbound (for some websites)
  egress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP outbound for web scraping"
  }

  # MongoDB access (if using external MongoDB)
  egress {
    from_port   = 27017
    to_port     = 27017
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "MongoDB access"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-lambda-sg"
  })
}

# Lambda Function
resource "aws_lambda_function" "business_scraper" {
  function_name = "${var.lambda_function_name}-${var.environment}"
  role         = aws_iam_role.lambda_role.arn
  package_type = "Image"
  image_uri    = "${aws_ecr_repository.business_scraper.repository_url}:${var.container_image_tag}"

  timeout     = var.lambda_timeout
  memory_size = var.lambda_memory_size

  ephemeral_storage {
    size = var.lambda_ephemeral_storage
  }

  environment {
    variables = {
      PLAYWRIGHT_HEADLESS         = "true"
      LAMBDA_ENVIRONMENT         = "true"
      MONGODB_CONNECTION_STRING  = var.mongodb_connection_string
      MONGODB_DATABASE          = var.mongodb_database
      ENVIRONMENT               = var.environment
    }
  }

  # VPC configuration (if enabled)
  dynamic "vpc_config" {
    for_each = var.enable_vpc ? [1] : []
    content {
      subnet_ids         = var.vpc_subnet_ids
      security_group_ids = concat(var.vpc_security_group_ids, [aws_security_group.lambda_sg[0].id])
    }
  }

  # X-Ray tracing (if enabled)
  dynamic "tracing_config" {
    for_each = var.enable_xray_tracing ? [1] : []
    content {
      mode = "Active"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.lambda_logs,
  ]

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-lambda"
  })
}

# Lambda Function URL (alternative to API Gateway)
resource "aws_lambda_function_url" "business_scraper" {
  count              = var.enable_api_gateway ? 0 : 1
  function_name      = aws_lambda_function.business_scraper.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST"]
    allow_headers     = ["date", "keep-alive", "content-type", "authorization", "x-api-key"]
    expose_headers    = ["date", "keep-alive"]
    max_age          = 86400
  }
}

# EventBridge Rule for Scheduled Execution
resource "aws_cloudwatch_event_rule" "lambda_schedule" {
  count               = var.enable_scheduled_execution ? 1 : 0
  name                = "${var.project_name}-${var.environment}-schedule"
  description         = "Scheduled execution for Business Scraper"
  schedule_expression = var.schedule_expression

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-schedule"
  })
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  count     = var.enable_scheduled_execution ? 1 : 0
  rule      = aws_cloudwatch_event_rule.lambda_schedule[0].name
  target_id = "BusinessScraperTarget"
  arn       = aws_lambda_function.business_scraper.arn

  input = jsonencode({
    search_query = var.default_search_query
    max_results  = var.default_max_results
  })
}

resource "aws_lambda_permission" "allow_eventbridge" {
  count         = var.enable_scheduled_execution ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.business_scraper.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule[0].arn
}