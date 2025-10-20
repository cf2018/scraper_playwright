#!/bin/bash

# Business Scraper Lambda Deployment Script
# This script handles the complete deployment pipeline from repo clone to Lambda deployment

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="${REPO_URL:-https://github.com/your-username/scraper_playwright.git}"
PROJECT_DIR="${PROJECT_DIR:-scraper_playwright}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
TERRAFORM_BACKEND_BUCKET="${TERRAFORM_BACKEND_BUCKET:-}"
TERRAFORM_BACKEND_KEY="${TERRAFORM_BACKEND_KEY:-business-scraper/terraform.tfstate}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check if required tools are installed
    local missing_tools=()
    
    command -v git >/dev/null 2>&1 || missing_tools+=("git")
    command -v docker >/dev/null 2>&1 || missing_tools+=("docker")
    command -v terraform >/dev/null 2>&1 || missing_tools+=("terraform")
    command -v aws >/dev/null 2>&1 || missing_tools+=("aws-cli")
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        echo "Please install the missing tools and try again."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log_error "AWS credentials not configured or invalid"
        echo "Please run 'aws configure' or set AWS environment variables"
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running"
        echo "Please start Docker and try again"
        exit 1
    fi
    
    log_success "All dependencies are available"
}

clone_or_update_repo() {
    log_info "Setting up repository..."
    
    if [ -d "$PROJECT_DIR" ]; then
        log_info "Repository exists, updating..."
        cd "$PROJECT_DIR"
        git fetch origin
        git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null
        cd ..
    else
        log_info "Cloning repository..."
        git clone "$REPO_URL" "$PROJECT_DIR"
    fi
    
    log_success "Repository is ready"
}

setup_terraform() {
    log_info "Setting up Terraform..."
    
    cd "$PROJECT_DIR/infra"
    
    # Create terraform.tfvars if it doesn't exist
    if [ ! -f "terraform.tfvars" ]; then
        log_info "Creating terraform.tfvars from example..."
        cp terraform.tfvars.example terraform.tfvars
        log_warning "Please edit infra/terraform.tfvars with your specific configuration"
    fi
    
    # Initialize Terraform
    log_info "Initializing Terraform..."
    if [ -n "$TERRAFORM_BACKEND_BUCKET" ]; then
        terraform init \
            -backend-config="bucket=$TERRAFORM_BACKEND_BUCKET" \
            -backend-config="key=$TERRAFORM_BACKEND_KEY" \
            -backend-config="region=$AWS_REGION"
    else
        terraform init
    fi
    
    # Validate configuration
    log_info "Validating Terraform configuration..."
    terraform validate
    
    # Format files
    terraform fmt -recursive
    
    cd ..
    log_success "Terraform is ready"
}

get_aws_account_info() {
    log_info "Getting AWS account information..."
    
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    AWS_REGION_CURRENT=$(aws configure get region || echo "$AWS_REGION")
    
    log_info "AWS Account ID: $AWS_ACCOUNT_ID"
    log_info "AWS Region: $AWS_REGION_CURRENT"
    
    export AWS_ACCOUNT_ID
    export AWS_REGION_CURRENT
}

plan_deployment() {
    log_info "Planning Terraform deployment..."
    
    cd "$PROJECT_DIR/infra"
    
    terraform plan \
        -var="environment=$ENVIRONMENT" \
        -var="aws_region=$AWS_REGION_CURRENT" \
        -out=tfplan
    
    cd ..
    log_success "Terraform plan completed"
}

deploy_infrastructure() {
    log_info "Deploying infrastructure..."
    
    cd "$PROJECT_DIR/infra"
    
    # Apply Terraform configuration
    terraform apply tfplan
    
    # Get outputs
    ECR_REPOSITORY_URL=$(terraform output -raw ecr_repository_url 2>/dev/null || echo "")
    LAMBDA_FUNCTION_NAME=$(terraform output -raw lambda_function_name 2>/dev/null || echo "")
    API_GATEWAY_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "")
    
    cd ..
    
    log_success "Infrastructure deployed successfully"
    
    if [ -n "$ECR_REPOSITORY_URL" ]; then
        log_info "ECR Repository: $ECR_REPOSITORY_URL"
    fi
    if [ -n "$LAMBDA_FUNCTION_NAME" ]; then
        log_info "Lambda Function: $LAMBDA_FUNCTION_NAME"
    fi
    if [ -n "$API_GATEWAY_URL" ]; then
        log_info "API Gateway URL: $API_GATEWAY_URL"
    fi
}

build_and_push_image() {
    log_info "Building and pushing Docker image..."
    
    cd "$PROJECT_DIR"
    
    # Get ECR repository URL from Terraform output
    cd infra
    ECR_REPOSITORY_URL=$(terraform output -raw ecr_repository_url 2>/dev/null)
    cd ..
    
    if [ -z "$ECR_REPOSITORY_URL" ]; then
        log_error "Could not get ECR repository URL from Terraform outputs"
        exit 1
    fi
    
    # Login to ECR
    log_info "Logging in to ECR..."
    aws ecr get-login-password --region "$AWS_REGION_CURRENT" | \
        docker login --username AWS --password-stdin "$ECR_REPOSITORY_URL"
    
    # Build image
    log_info "Building Docker image..."
    docker build -t business-scraper:latest .
    
    # Tag image
    IMAGE_TAG="${ECR_REPOSITORY_URL}:latest"
    docker tag business-scraper:latest "$IMAGE_TAG"
    
    # Push image
    log_info "Pushing image to ECR..."
    docker push "$IMAGE_TAG"
    
    log_success "Docker image pushed successfully"
    log_info "Image URI: $IMAGE_TAG"
}

update_lambda_function() {
    log_info "Updating Lambda function with new image..."
    
    cd "$PROJECT_DIR/infra"
    
    # Get Lambda function name
    LAMBDA_FUNCTION_NAME=$(terraform output -raw lambda_function_name 2>/dev/null)
    ECR_REPOSITORY_URL=$(terraform output -raw ecr_repository_url 2>/dev/null)
    
    if [ -n "$LAMBDA_FUNCTION_NAME" ] && [ -n "$ECR_REPOSITORY_URL" ]; then
        # Update Lambda function code
        aws lambda update-function-code \
            --function-name "$LAMBDA_FUNCTION_NAME" \
            --image-uri "${ECR_REPOSITORY_URL}:latest" \
            --region "$AWS_REGION_CURRENT"
        
        # Wait for update to complete
        log_info "Waiting for Lambda function update to complete..."
        aws lambda wait function-updated \
            --function-name "$LAMBDA_FUNCTION_NAME" \
            --region "$AWS_REGION_CURRENT"
        
        log_success "Lambda function updated successfully"
    else
        log_warning "Could not update Lambda function - missing outputs"
    fi
    
    cd ..
}

test_deployment() {
    log_info "Testing deployment..."
    
    cd "$PROJECT_DIR/infra"
    
    API_GATEWAY_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "")
    LAMBDA_FUNCTION_NAME=$(terraform output -raw lambda_function_name 2>/dev/null || echo "")
    
    # Test Lambda function directly
    if [ -n "$LAMBDA_FUNCTION_NAME" ]; then
        log_info "Testing Lambda function directly..."
        TEST_PAYLOAD='{"query": "test", "max_results": 1}'
        
        aws lambda invoke \
            --function-name "$LAMBDA_FUNCTION_NAME" \
            --payload "$TEST_PAYLOAD" \
            --region "$AWS_REGION_CURRENT" \
            /tmp/lambda_response.json >/dev/null
        
        if [ $? -eq 0 ]; then
            log_success "Lambda function test passed"
            log_info "Response: $(cat /tmp/lambda_response.json)"
        else
            log_warning "Lambda function test failed"
        fi
    fi
    
    # Test API Gateway if available
    if [ -n "$API_GATEWAY_URL" ]; then
        log_info "Testing API Gateway..."
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_GATEWAY_URL/health" || echo "000")
        
        if [ "$HTTP_STATUS" = "200" ]; then
            log_success "API Gateway test passed"
        else
            log_warning "API Gateway test failed (HTTP $HTTP_STATUS)"
        fi
    fi
    
    cd ..
}

show_deployment_info() {
    log_info "Deployment Summary"
    echo "===================="
    
    cd "$PROJECT_DIR/infra"
    
    # Show all Terraform outputs
    terraform output 2>/dev/null || log_warning "No Terraform outputs available"
    
    cd ..
    
    echo ""
    log_info "Next steps:"
    echo "1. Test your Lambda function using the AWS console or CLI"
    echo "2. Monitor logs in CloudWatch: /aws/lambda/<function-name>"
    echo "3. Check API Gateway endpoints if enabled"
    echo "4. Set up monitoring alerts if needed"
}

# Main deployment flow
main() {
    log_info "Starting Business Scraper Lambda Deployment"
    echo "=============================================="
    
    # Parse command line arguments
    SKIP_REPO_CLONE=false
    SKIP_INFRASTRUCTURE=false
    SKIP_IMAGE_BUILD=false
    PLAN_ONLY=false
    
    for arg in "$@"; do
        case $arg in
            --skip-repo-clone)
                SKIP_REPO_CLONE=true
                shift
                ;;
            --skip-infrastructure)
                SKIP_INFRASTRUCTURE=true
                shift
                ;;
            --skip-image-build)
                SKIP_IMAGE_BUILD=true
                shift
                ;;
            --plan-only)
                PLAN_ONLY=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --skip-repo-clone      Skip repository cloning/updating"
                echo "  --skip-infrastructure  Skip Terraform infrastructure deployment"
                echo "  --skip-image-build     Skip Docker image build and push"
                echo "  --plan-only           Only run terraform plan, don't apply"
                echo "  --help                Show this help message"
                echo ""
                echo "Environment Variables:"
                echo "  REPO_URL              Repository URL to clone"
                echo "  PROJECT_DIR           Directory name for the project"
                echo "  AWS_REGION            AWS region for deployment"
                echo "  ENVIRONMENT           Environment name (dev/staging/prod)"
                echo "  TERRAFORM_BACKEND_BUCKET  S3 bucket for Terraform state"
                echo "  TERRAFORM_BACKEND_KEY     S3 key for Terraform state"
                exit 0
                ;;
            *)
                log_error "Unknown option: $arg"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Step 1: Check dependencies
    check_dependencies
    
    # Step 2: Clone or update repository
    if [ "$SKIP_REPO_CLONE" = false ]; then
        clone_or_update_repo
    fi
    
    # Step 3: Get AWS account information
    get_aws_account_info
    
    # Step 4: Setup Terraform
    if [ "$SKIP_INFRASTRUCTURE" = false ]; then
        setup_terraform
        plan_deployment
        
        if [ "$PLAN_ONLY" = false ]; then
            deploy_infrastructure
        else
            log_info "Plan-only mode: Skipping infrastructure deployment"
            exit 0
        fi
    fi
    
    # Step 5: Build and push Docker image
    if [ "$SKIP_IMAGE_BUILD" = false ]; then
        build_and_push_image
        update_lambda_function
    fi
    
    # Step 6: Test deployment
    test_deployment
    
    # Step 7: Show summary
    show_deployment_info
    
    log_success "Deployment completed successfully!"
}

# Run main function with all arguments
main "$@"