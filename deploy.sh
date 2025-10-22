#!/bin/bash
# Build and Deploy Script for AWS Lambda Business Scraper

set -e

# Configuration
DOCKER_IMAGE_NAME="business-scraper-lambda"
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPOSITORY="${ECR_REPOSITORY:-}"  # Will be auto-created if not set
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-business-scraper}"
PROJECT_NAME="${PROJECT_NAME:-business-scraper}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

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

# Create or update ECR repository
setup_ecr_repository() {
    echo_info "Setting up ECR repository..."
    
    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    # Generate ECR repository name if not provided
    if [ -z "$ECR_REPOSITORY" ]; then
        ECR_REPO_NAME="${PROJECT_NAME}-${ENVIRONMENT}"
        ECR_REPOSITORY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
        echo_info "Generated ECR repository: $ECR_REPOSITORY"
    else
        # Extract repository name from URI
        ECR_REPO_NAME=$(echo "$ECR_REPOSITORY" | sed 's|.*/||')
    fi
    
    # Check if repository exists
    if aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
        echo_info "ECR repository '$ECR_REPO_NAME' already exists"
    else
        echo_info "Creating ECR repository '$ECR_REPO_NAME'..."
        
        # Create repository
        aws ecr create-repository \
            --repository-name "$ECR_REPO_NAME" \
            --region "$AWS_REGION" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256
        
        # Set lifecycle policy to manage image retention
        cat > lifecycle-policy.json << EOF
{
    "rules": [
        {
            "rulePriority": 1,
            "description": "Keep last 10 images",
            "selection": {
                "tagStatus": "any",
                "countType": "imageCountMoreThan",
                "countNumber": 10
            },
            "action": {
                "type": "expire"
            }
        }
    ]
}
EOF
        
        aws ecr put-lifecycle-policy \
            --repository-name "$ECR_REPO_NAME" \
            --lifecycle-policy-text file://lifecycle-policy.json \
            --region "$AWS_REGION"
        
        rm lifecycle-policy.json
        
        echo_success "ECR repository created: $ECR_REPOSITORY"
    fi
    
    # Export for use in other functions
    export ECR_REPOSITORY
    export ECR_REPO_NAME
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
    echo_info "Deploying to AWS Lambda..."
    
    # Setup ECR repository first
    setup_ecr_repository
    
    # Login to ECR
    echo_info "Logging into ECR..."
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPOSITORY
    
    # Tag and push image
    echo_info "Tagging and pushing image to ECR..."
    docker tag $DOCKER_IMAGE_NAME:latest $ECR_REPOSITORY:latest
    docker push $ECR_REPOSITORY:latest
    
    # Check if Lambda function exists
    if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION >/dev/null 2>&1; then
        echo_info "Updating existing Lambda function..."
        aws lambda update-function-code \
            --function-name $LAMBDA_FUNCTION_NAME \
            --image-uri $ECR_REPOSITORY:latest \
            --region $AWS_REGION
        
        # Wait for update to complete
        echo_info "Waiting for Lambda function update to complete..."
        aws lambda wait function-updated \
            --function-name $LAMBDA_FUNCTION_NAME \
            --region $AWS_REGION
    else
        echo_warning "Lambda function '$LAMBDA_FUNCTION_NAME' does not exist. Creating it..."
        create_lambda_internal
    fi
    
    echo_success "Lambda function deployment completed!"
    
    # Show function info
    echo_info "Function details:"
    aws lambda get-function \
        --function-name $LAMBDA_FUNCTION_NAME \
        --region $AWS_REGION \
        --query '{FunctionName:Configuration.FunctionName,Runtime:Configuration.PackageType,LastModified:Configuration.LastModified,State:Configuration.State}' \
        --output table
}

# Create Lambda function (first time only)
create_lambda() {
    setup_ecr_repository
    create_lambda_internal
}

# Internal function to create Lambda function
create_lambda_internal() {
    echo_info "Creating new Lambda function..."
    
    # Create execution role (if doesn't exist)
    ROLE_NAME="lambda-${PROJECT_NAME}-${ENVIRONMENT}-role"
    ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null || echo "")
    
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
            --role-name "$ROLE_NAME" \
            --assume-role-policy-document file://trust-policy.json \
            --tags Key=Project,Value="$PROJECT_NAME" Key=Environment,Value="$ENVIRONMENT"
        
        # Attach basic execution policy
        aws iam attach-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
        
        # Attach VPC execution policy (if Lambda needs VPC access)
        aws iam attach-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
        
        rm trust-policy.json
        
        ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
        echo_info "Created role: $ROLE_ARN"
        
        # Wait for role to be available
        echo_info "Waiting for IAM role to be available..."
        sleep 15
    fi
    
    # Create Lambda function
    echo_info "Creating Lambda function '$LAMBDA_FUNCTION_NAME'..."
    aws lambda create-function \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --role "$ROLE_ARN" \
        --code ImageUri="$ECR_REPOSITORY:latest" \
        --package-type Image \
        --timeout 300 \
        --memory-size 1024 \
        --environment Variables="{PLAYWRIGHT_HEADLESS=true,LAMBDA_ENVIRONMENT=true}" \
        --tags Project="$PROJECT_NAME",Environment="$ENVIRONMENT" \
        --region "$AWS_REGION"
    
    echo_success "Lambda function created successfully!"
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker image"
    echo "  test        Test Docker image locally"
    echo "  deploy      Deploy to AWS Lambda (creates ECR repo and Lambda function if needed)"
    echo "  create      Create new Lambda function with ECR repository"
    echo "  all         Build, test, and deploy"
    echo ""
    echo "Options:"
    echo "  -h, --help  Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  ECR_REPOSITORY       ECR repository URI (optional - will be auto-created)"
    echo "  AWS_REGION           AWS region (default: us-east-1)"
    echo "  LAMBDA_FUNCTION_NAME Lambda function name (default: business-scraper)"
    echo "  PROJECT_NAME         Project name for tagging (default: business-scraper)"
    echo "  ENVIRONMENT          Environment name (default: dev)"
    echo ""
    echo "Examples:"
    echo "  $0 deploy                              # Deploy with defaults"
    echo "  ENVIRONMENT=prod $0 deploy             # Deploy to production"
    echo "  AWS_REGION=us-west-2 $0 all           # Deploy to different region"
}

# Main script
main() {
    case "$1" in
        build)
            check_prerequisites
            build_image
            ;;
        test)
            check_prerequisites
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
        -h|--help|"")
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