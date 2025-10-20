# AWS Lambda Deployment Guide

This guide explains how to deploy the Business Scraper to AWS Lambda for serverless execution.

## 🚀 Quick Deployment

### Option 1: Using the Build Script (Recommended)
```bash
# Set your ECR repository URI
export ECR_REPOSITORY="123456789012.dkr.ecr.us-east-1.amazonaws.com/business-scraper"

# Build, test, and deploy
./deploy.sh all
```

### Option 2: Manual Deployment
```bash
# 1. Build Docker image
docker build -t business-scraper-lambda .

# 2. Test locally
docker run --rm -p 9000:8080 business-scraper-lambda

# 3. Push to ECR and deploy (see detailed steps below)
```

## 📋 Prerequisites

### Required Tools
- **Docker**: For building container images
- **AWS CLI**: For deployment and management
- **AWS Account**: With appropriate permissions

### AWS Permissions Required
Your AWS user/role needs these permissions:
- `lambda:*` (Lambda function management)
- `ecr:*` (Container registry access)  
- `iam:CreateRole`, `iam:AttachRolePolicy` (IAM role creation)
- `apigateway:*` (API Gateway for HTTP endpoints)

### AWS Setup
```bash
# Configure AWS CLI
aws configure

# Login to ECR (replace with your region and account)
aws ecr get-login-password --region us-east-1 | \
docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
```

## 🏗️ Architecture

### Lambda Function Features
- **Automatic Headless Mode**: Detects Lambda environment automatically
- **Optimized Browser Settings**: Memory and CPU optimized for serverless
- **Individual Database Saves**: Each business saved separately (no timeouts)
- **Error Handling**: Comprehensive error catching and reporting
- **JSON Response**: Clean, structured API responses

### Environment Detection
The scraper automatically detects Lambda environment and switches to:
- Headless browser mode
- Reduced timeouts (30s default)
- No slow motion delays
- Optimized memory usage
- Disabled debug screenshots

## 📦 Container Configuration

### Environment Variables
```bash
PLAYWRIGHT_HEADLESS=true          # Force headless mode
LAMBDA_ENVIRONMENT=true           # Lambda detection flag
MONGODB_CONNECTION_STRING=...     # Optional: MongoDB connection
MONGODB_DATABASE=business_scraper # Database name
```

### Lambda Settings
- **Runtime**: Container (Python 3.12)
- **Memory**: 1024 MB (minimum for browser)
- **Timeout**: 300 seconds (5 minutes maximum)
- **Storage**: 512 MB ephemeral storage

## 🔧 API Usage

### Invoke Lambda Function
```bash
# Direct Lambda invocation
aws lambda invoke \
  --function-name business-scraper \
  --payload '{"search_query":"registro de marcas","max_results":10}' \
  response.json

# View response
cat response.json
```

### HTTP API (via API Gateway)
```bash
# POST request to scrape businesses
curl -X POST https://your-api-gateway-url/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "search_query": "registro de marcas en buenos aires",
    "max_results": 20
  }'

# Health check
curl https://your-api-gateway-url/health
```

### Request Parameters
```json
{
  "search_query": "registro de marcas en buenos aires",  // Required
  "max_results": 50,                                     // Optional (default: 50, max: 100)
  "timeout": 30000                                       // Optional (milliseconds, max: 60000)
}
```

### Response Format
```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "message": "Successfully scraped 15 businesses",
    "data": {
      "results_count": 15,
      "search_query": "registro de marcas en buenos aires",
      "execution_time_seconds": 45.2,
      "scraping_time_seconds": 42.1,
      "businesses": [
        {
          "_id": "unique-id",
          "name": "Business Name",
          "phone": "+1234567890",
          "website": "https://example.com",
          "email": "contact@business.com",
          "address": "123 Street, City",
          "rating": "4.5",
          "reviews": "100",
          "search_keyword": "registro de marcas en buenos aires",
          "contacted": false,
          "created_at": "2024-01-01T12:00:00Z"
        }
      ]
    }
  }
}
```

## 🛠️ Deployment Steps

### 1. Create ECR Repository
```bash
# Create repository
aws ecr create-repository \
  --repository-name business-scraper \
  --region us-east-1

# Get repository URI
ECR_URI=$(aws ecr describe-repositories \
  --repository-names business-scraper \
  --query 'repositories[0].repositoryUri' \
  --output text)

echo "ECR Repository: $ECR_URI"
```

### 2. Build and Push Image
```bash
# Build image
docker build -t business-scraper-lambda .

# Tag for ECR
docker tag business-scraper-lambda:latest $ECR_URI:latest

# Push to ECR
docker push $ECR_URI:latest
```

### 3. Create Lambda Function
```bash
# Create execution role
aws iam create-role \
  --role-name lambda-scraper-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name lambda-scraper-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Get role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name lambda-scraper-role \
  --query 'Role.Arn' --output text)

# Create Lambda function
aws lambda create-function \
  --function-name business-scraper \
  --role $ROLE_ARN \
  --code ImageUri=$ECR_URI:latest \
  --package-type Image \
  --timeout 300 \
  --memory-size 1024 \
  --environment Variables='{
    PLAYWRIGHT_HEADLESS=true,
    LAMBDA_ENVIRONMENT=true
  }'
```

### 4. Create API Gateway (Optional)
```bash
# Create REST API
aws apigateway create-rest-api \
  --name business-scraper-api \
  --description "Business Scraper API"

# Configure API Gateway integration (see AWS documentation)
```

## 🧪 Testing

### Local Testing
```bash
# Test with Docker locally
docker run --rm -p 9000:8080 -e LAMBDA_ENVIRONMENT=true business-scraper-lambda

# Send test request
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"search_query":"registro de marcas","max_results":5}'
```

### Lambda Testing
```bash
# Create test event
echo '{
  "search_query": "registro de marcas en buenos aires",
  "max_results": 10
}' > test-event.json

# Invoke function
aws lambda invoke \
  --function-name business-scraper \
  --payload file://test-event.json \
  --cli-binary-format raw-in-base64-out \
  response.json

# Check response
cat response.json | jq .
```

## 📊 Monitoring

### CloudWatch Logs
```bash
# View logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/business-scraper"

# Tail logs
aws logs tail /aws/lambda/business-scraper --follow
```

### Metrics to Monitor
- **Duration**: Function execution time
- **Memory Usage**: Peak memory consumption
- **Error Rate**: Failed invocations
- **Throttles**: Rate limiting events

## 🔧 Troubleshooting

### Common Issues

**Function Timeout**
```bash
# Increase timeout (max 15 minutes)
aws lambda update-function-configuration \
  --function-name business-scraper \
  --timeout 600
```

**Memory Issues**
```bash
# Increase memory allocation
aws lambda update-function-configuration \
  --function-name business-scraper \
  --memory-size 2048
```

**Browser Launch Failures**
- Ensure container has required system dependencies
- Check Lambda execution role permissions
- Verify headless mode is enabled

**Database Connection Issues**
- Function falls back to JSON storage automatically
- Check MongoDB connection string in environment variables
- Verify network connectivity (VPC configuration if needed)

### Debug Mode
```bash
# Enable detailed logging
aws lambda update-function-configuration \
  --function-name business-scraper \
  --environment Variables='{
    PLAYWRIGHT_HEADLESS=true,
    LAMBDA_ENVIRONMENT=true,
    DEBUG=true
  }'
```

## 💰 Cost Optimization

### Pricing Factors
- **Invocation Duration**: Longer scraping = higher cost
- **Memory Allocation**: 1GB minimum for browser operations
- **Requests**: Number of function invocations

### Cost Reduction Strategies
1. **Batch Processing**: Process multiple queries per invocation
2. **Concurrent Execution**: Limit to avoid throttling charges
3. **Memory Tuning**: Find optimal memory/performance balance
4. **Scheduled Execution**: Use EventBridge for regular scraping

## 🚀 Advanced Configuration

### VPC Configuration (Optional)
For private MongoDB access:
```bash
aws lambda update-function-configuration \
  --function-name business-scraper \
  --vpc-config SubnetIds=subnet-12345,SecurityGroupIds=sg-12345
```

### Layer Usage (Alternative)
Consider using Chrome AWS Lambda layer:
```bash
# Add Chrome layer
aws lambda update-function-configuration \
  --function-name business-scraper \
  --layers arn:aws:lambda:us-east-1:764866452798:layer:chrome-aws-lambda:31
```

### Environment-Specific Deployments
```bash
# Production deployment
export ENVIRONMENT=prod
export ECR_REPOSITORY=$PROD_ECR_URI
./deploy.sh deploy

# Staging deployment  
export ENVIRONMENT=staging
export ECR_REPOSITORY=$STAGING_ECR_URI
./deploy.sh deploy
```

## 📚 Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Playwright Docker Guide](https://playwright.dev/python/docs/docker)
- [ECR User Guide](https://docs.aws.amazon.com/ecr/)
- [API Gateway Integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-integrations.html)

---

**Last Updated**: December 2024  
**Tested With**: AWS Lambda Python 3.12 Runtime  
**Container Size**: ~2GB (optimized for Lambda)