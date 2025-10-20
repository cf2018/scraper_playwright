# Terraform deployment and management scripts

# This file contains example Terraform commands and deployment workflows
# Run these commands from the infra/ directory

# Initialize Terraform (run first time or after adding new providers)
# terraform init

# Validate Terraform configuration
# terraform validate

# Plan deployment (see what will be created/changed)
# terraform plan

# Apply changes (deploy infrastructure)
# terraform apply

# Destroy infrastructure (cleanup)
# terraform destroy

# Format Terraform files
# terraform fmt -recursive

# Show current state
# terraform show

# List resources in state
# terraform state list

# Import existing AWS resources (if needed)
# terraform import aws_lambda_function.business_scraper <function-name>

# Variables can be set in multiple ways:
# 1. Create terraform.tfvars file:
#    environment = "prod"
#    aws_region = "us-west-2"
#    lambda_memory_size = 2048
#    mongodb_connection_string = "mongodb+srv://..."

# 2. Use command line variables:
#    terraform apply -var="environment=prod" -var="aws_region=us-west-2"

# 3. Set environment variables:
#    export TF_VAR_environment=prod
#    export TF_VAR_aws_region=us-west-2

# Example deployment workflow for different environments:

# Development environment
# terraform workspace new dev || terraform workspace select dev
# terraform apply -var="environment=dev" -var="lambda_memory_size=512"

# Production environment
# terraform workspace new prod || terraform workspace select prod
# terraform apply -var="environment=prod" -var="lambda_memory_size=1024" -var="enable_cloudwatch_alarms=true"

# ECR repository will be created automatically
# After infrastructure is deployed, build and push Docker image:
# 1. Get ECR login token:
#    aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com

# 2. Build and tag image:
#    docker build -t business-scraper .
#    docker tag business-scraper:latest <account-id>.dkr.ecr.<region>.amazonaws.com/<repository-name>:latest

# 3. Push image:
#    docker push <account-id>.dkr.ecr.<region>.amazonaws.com/<repository-name>:latest

# 4. Update Lambda function to use new image:
#    terraform apply -refresh-only

# Monitoring and troubleshooting:
# - CloudWatch Logs: /aws/lambda/<function-name>
# - CloudWatch Metrics: AWS/Lambda namespace
# - X-Ray Tracing: Enable with enable_xray_tracing = true
# - API Gateway Logs: /aws/apigateway/<api-name>

# Cost optimization tips:
# - Use smaller memory sizes for Lambda if possible
# - Set appropriate log retention periods
# - Use scheduled execution instead of API Gateway if real-time access isn't needed
# - Consider using Provisioned Concurrency only for production high-traffic scenarios