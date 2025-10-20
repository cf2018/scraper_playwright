#!/bin/bash
# Build and Deploy Script for AWS Lambda Business Scraper

set -e

# Configuration
DOCKER_IMAGE_NAME="business-scraper-lambda"
AWS_REGION="us-east-1"
ECR_REPOSITORY=""  # Set this to your ECR repository URI
LAMBDA_FUNCTION_NAME="business-scraper"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
echo_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
echo_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites..."
    
    if ! command_exists docker; then
        echo_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command_exists aws; then
        echo_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    fi
    
    # Check if logged into AWS
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        echo_error "Not logged into AWS. Please run 'aws configure' first."
        exit 1
    fi
    
    echo_success "Prerequisites check passed!"
}

# Build Docker image
build_image() {
    echo_info "Building Docker image for Lambda..."
    
    # Create .dockerignore if it doesn't exist
    if [ ! -f .dockerignore ]; then
        cat > .dockerignore << EOF
.git
.gitignore
README.md
.env
venv/
__pycache__/
*.pyc
.pytest_cache/
.vscode/
node_modules/
*.log
dashboard.py
templates/
manage_businesses.py
EOF
        echo_info "Created .dockerignore file"
    fi
    
    docker build -t $DOCKER_IMAGE_NAME .
    echo_success "Docker image built successfully!"
}

# Test Docker image locally
test_local() {
    echo_info "Testing Docker image locally..."
    
    # Create test event
    cat > test_event.json << EOF
{
    "search_query": "registro de marcas en buenos aires",
    "max_results": 5
}
EOF
    
    echo_info "Starting local Lambda test..."
    docker run --rm \
        -p 9000:8080 \
        -e LAMBDA_ENVIRONMENT=true \
        $DOCKER_IMAGE_NAME &
    
    DOCKER_PID=$!
    sleep 5
    
    # Test the function
    echo_info "Sending test request..."
    curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
         -d @test_event.json \
         --max-time 60 || true
    
    # Stop the container
    kill $DOCKER_PID 2>/dev/null || true
    rm test_event.json
    
    echo_success "Local test completed!"
}

# Deploy to AWS Lambda
deploy_lambda() {
    if [ -z "$ECR_REPOSITORY" ]; then
        echo_error "ECR_REPOSITORY is not set. Please set it to your ECR repository URI."
        echo_info "Example: 123456789012.dkr.ecr.us-east-1.amazonaws.com/business-scraper"
        exit 1
    fi
    
    echo_info "Deploying to AWS Lambda..."
    
    # Login to ECR
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPOSITORY
    
    # Tag and push image
    docker tag $DOCKER_IMAGE_NAME:latest $ECR_REPOSITORY:latest
    docker push $ECR_REPOSITORY:latest
    
    # Update Lambda function
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNCTION_NAME \
        --image-uri $ECR_REPOSITORY:latest \
        --region $AWS_REGION
    
    echo_success "Lambda function updated successfully!"
}

# Create Lambda function (first time only)
create_lambda() {
    if [ -z "$ECR_REPOSITORY" ]; then
        echo_error "ECR_REPOSITORY is not set. Please set it to your ECR repository URI."
        exit 1
    fi
    
    echo_info "Creating new Lambda function..."
    
    # Create execution role (if doesn't exist)
    ROLE_ARN=$(aws iam get-role --role-name lambda-scraper-role --query 'Role.Arn' --output text 2>/dev/null || echo "")
    
    if [ -z "$ROLE_ARN" ]; then
        echo_info "Creating Lambda execution role..."
        
        # Create trust policy
        cat > trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF
        
        aws iam create-role \
            --role-name lambda-scraper-role \
            --assume-role-policy-document file://trust-policy.json
        
        aws iam attach-role-policy \
            --role-name lambda-scraper-role \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
        
        rm trust-policy.json
        
        ROLE_ARN=$(aws iam get-role --role-name lambda-scraper-role --query 'Role.Arn' --output text)
        echo_info "Created role: $ROLE_ARN"
        
        # Wait for role to be available
        sleep 10
    fi
    
    # Create Lambda function
    aws lambda create-function \
        --function-name $LAMBDA_FUNCTION_NAME \
        --role $ROLE_ARN \
        --code ImageUri=$ECR_REPOSITORY:latest \
        --package-type Image \
        --timeout 300 \
        --memory-size 1024 \
        --environment Variables='{PLAYWRIGHT_HEADLESS=true,LAMBDA_ENVIRONMENT=true}' \
        --region $AWS_REGION
    
    echo_success "Lambda function created successfully!"
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker image"
    echo "  test        Test Docker image locally"
    echo "  deploy      Deploy to AWS Lambda (update existing function)"
    echo "  create      Create new Lambda function"
    echo "  all         Build, test, and deploy"
    echo ""
    echo "Options:"
    echo "  -h, --help  Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  ECR_REPOSITORY      ECR repository URI (required for deploy/create)"
    echo "  AWS_REGION          AWS region (default: us-east-1)"
    echo "  LAMBDA_FUNCTION_NAME Lambda function name (default: business-scraper)"
}

# Main script
main() {
    case "$1" in
        build)
            check_prerequisites
            build_image
            ;;
        test)
            build_image
            test_local
            ;;
        deploy)
            check_prerequisites
            build_image
            deploy_lambda
            ;;
        create)
            check_prerequisites
            build_image
            create_lambda
            ;;
        all)
            check_prerequisites
            build_image
            test_local
            deploy_lambda
            ;;
        -h|--help)
            show_usage
            ;;
        *)
            echo_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"