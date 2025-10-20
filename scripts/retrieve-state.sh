#!/bin/bash

# Business Scraper State Management Script
# This script helps retrieve, manage, and restore Terraform state and deployment information

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
STATE_BACKUP_DIR="${STATE_BACKUP_DIR:-./terraform-backups}"

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
    
    local missing_tools=()
    
    command -v git >/dev/null 2>&1 || missing_tools+=("git")
    command -v terraform >/dev/null 2>&1 || missing_tools+=("terraform")
    command -v aws >/dev/null 2>&1 || missing_tools+=("aws-cli")
    command -v jq >/dev/null 2>&1 || missing_tools+=("jq")
    
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
    
    log_success "All dependencies are available"
}

clone_repo_if_needed() {
    log_info "Setting up repository..."
    
    if [ ! -d "$PROJECT_DIR" ]; then
        log_info "Cloning repository..."
        git clone "$REPO_URL" "$PROJECT_DIR"
        log_success "Repository cloned"
    else
        log_info "Repository already exists"
    fi
}

setup_terraform_backend() {
    log_info "Setting up Terraform backend..."
    
    cd "$PROJECT_DIR/infra"
    
    # Initialize Terraform with backend
    if [ -n "$TERRAFORM_BACKEND_BUCKET" ]; then
        log_info "Initializing with remote backend..."
        terraform init \
            -backend-config="bucket=$TERRAFORM_BACKEND_BUCKET" \
            -backend-config="key=$TERRAFORM_BACKEND_KEY" \
            -backend-config="region=$AWS_REGION"
    else
        log_info "Initializing with local backend..."
        terraform init
    fi
    
    cd ..
    log_success "Terraform backend initialized"
}

show_current_state() {
    log_info "Current Terraform State"
    echo "======================="
    
    cd "$PROJECT_DIR/infra"
    
    # Check if state exists
    if terraform state list >/dev/null 2>&1; then
        echo ""
        log_info "Resources in state:"
        terraform state list
        
        echo ""
        log_info "Current outputs:"
        terraform output 2>/dev/null || log_warning "No outputs available"
        
        echo ""
        log_info "State file info:"
        terraform show -json | jq -r '.terraform_version // "unknown"' | xargs -I {} echo "Terraform version: {}"
        terraform show -json | jq -r '.serial // "unknown"' | xargs -I {} echo "State serial: {}"
        
    else
        log_warning "No Terraform state found"
    fi
    
    cd ..
}

backup_state() {
    log_info "Backing up Terraform state..."
    
    # Create backup directory
    mkdir -p "$STATE_BACKUP_DIR"
    
    cd "$PROJECT_DIR/infra"
    
    # Create timestamp
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="$STATE_BACKUP_DIR/terraform_state_${ENVIRONMENT}_${TIMESTAMP}.tfstate"
    
    # Pull and backup state
    if terraform state pull > "$BACKUP_FILE" 2>/dev/null; then
        log_success "State backed up to: $BACKUP_FILE"
        
        # Also backup as latest
        cp "$BACKUP_FILE" "$STATE_BACKUP_DIR/terraform_state_${ENVIRONMENT}_latest.tfstate"
        
        # Show backup info
        echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
        echo "Resources count: $(cat "$BACKUP_FILE" | jq '.resources | length' 2>/dev/null || echo "unknown")"
    else
        log_warning "No state to backup or state is empty"
    fi
    
    cd ..
}

restore_state() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        log_error "Please specify a backup file to restore"
        echo "Available backups:"
        ls -la "$STATE_BACKUP_DIR"/*.tfstate 2>/dev/null || echo "No backups found"
        return 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    log_warning "This will overwrite the current Terraform state!"
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "State restore cancelled"
        return 0
    fi
    
    cd "$PROJECT_DIR/infra"
    
    log_info "Restoring state from: $backup_file"
    
    # Push state
    if terraform state push "$backup_file"; then
        log_success "State restored successfully"
        
        # Verify restoration
        log_info "Verifying restored state..."
        terraform state list
    else
        log_error "Failed to restore state"
        return 1
    fi
    
    cd ..
}

show_aws_resources() {
    log_info "AWS Resources Status"
    echo "==================="
    
    # Get AWS account info
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    log_info "AWS Account: $AWS_ACCOUNT_ID"
    log_info "AWS Region: $AWS_REGION"
    
    echo ""
    log_info "Lambda Functions:"
    aws lambda list-functions \
        --region "$AWS_REGION" \
        --query "Functions[?contains(FunctionName, 'business-scraper') || contains(FunctionName, 'scraper')].{Name:FunctionName,Runtime:Runtime,LastModified:LastModified}" \
        --output table 2>/dev/null || log_warning "No matching Lambda functions found"
    
    echo ""
    log_info "ECR Repositories:"
    aws ecr describe-repositories \
        --region "$AWS_REGION" \
        --query "repositories[?contains(repositoryName, 'business-scraper') || contains(repositoryName, 'scraper')].{Name:repositoryName,URI:repositoryUri,CreatedAt:createdAt}" \
        --output table 2>/dev/null || log_warning "No matching ECR repositories found"
    
    echo ""
    log_info "API Gateways:"
    aws apigateway get-rest-apis \
        --region "$AWS_REGION" \
        --query "items[?contains(name, 'business-scraper') || contains(name, 'scraper')].{Name:name,Id:id,CreatedDate:createdDate}" \
        --output table 2>/dev/null || log_warning "No matching API Gateways found"
    
    echo ""
    log_info "CloudWatch Log Groups:"
    aws logs describe-log-groups \
        --region "$AWS_REGION" \
        --log-group-name-prefix "/aws/lambda" \
        --query "logGroups[?contains(logGroupName, 'business-scraper') || contains(logGroupName, 'scraper')].{Name:logGroupName,Size:storedBytes,RetentionDays:retentionInDays}" \
        --output table 2>/dev/null || log_warning "No matching log groups found"
}

import_existing_resources() {
    log_info "Importing existing AWS resources into Terraform state..."
    
    cd "$PROJECT_DIR/infra"
    
    # Function to safely import resource
    import_resource() {
        local tf_resource="$1"
        local aws_resource="$2"
        
        log_info "Importing $tf_resource..."
        if terraform import "$tf_resource" "$aws_resource" 2>/dev/null; then
            log_success "Imported $tf_resource"
        else
            log_warning "Could not import $tf_resource (may not exist or already imported)"
        fi
    }
    
    # Try to import common resources
    # Note: These are examples - adjust based on your actual resource names
    
    # Lambda function
    LAMBDA_FUNCTION_NAME="business-scraper-${ENVIRONMENT}"
    import_resource "aws_lambda_function.business_scraper" "$LAMBDA_FUNCTION_NAME"
    
    # ECR repository
    ECR_REPO_NAME="business-scraper-${ENVIRONMENT}"
    import_resource "aws_ecr_repository.business_scraper" "$ECR_REPO_NAME"
    
    # IAM role
    IAM_ROLE_NAME="business-scraper-${ENVIRONMENT}-lambda-role"
    import_resource "aws_iam_role.lambda_execution_role" "$IAM_ROLE_NAME"
    
    # CloudWatch log group
    LOG_GROUP_NAME="/aws/lambda/$LAMBDA_FUNCTION_NAME"
    import_resource "aws_cloudwatch_log_group.lambda_logs" "$LOG_GROUP_NAME"
    
    cd ..
    log_info "Import process completed"
}

validate_state() {
    log_info "Validating Terraform state and configuration..."
    
    cd "$PROJECT_DIR/infra"
    
    # Validate configuration
    if terraform validate; then
        log_success "Terraform configuration is valid"
    else
        log_error "Terraform configuration validation failed"
        cd ..
        return 1
    fi
    
    # Plan to check for drift
    log_info "Checking for configuration drift..."
    if terraform plan -detailed-exitcode >/dev/null 2>&1; then
        log_success "Infrastructure matches configuration (no changes needed)"
    elif [ $? -eq 2 ]; then
        log_warning "Infrastructure drift detected - changes are needed"
        echo "Run 'terraform plan' to see the differences"
    else
        log_error "Error occurred during plan"
    fi
    
    cd ..
}

show_logs() {
    local function_name="$1"
    local lines="${2:-50}"
    
    if [ -z "$function_name" ]; then
        # Try to get function name from Terraform output
        cd "$PROJECT_DIR/infra"
        function_name=$(terraform output -raw lambda_function_name 2>/dev/null || echo "")
        cd ..
        
        if [ -z "$function_name" ]; then
            log_error "Please specify Lambda function name"
            echo "Usage: $0 logs <function-name> [lines]"
            return 1
        fi
    fi
    
    log_info "Showing last $lines lines from Lambda function: $function_name"
    echo "================================================"
    
    aws logs tail "/aws/lambda/$function_name" \
        --since 1h \
        --follow \
        --region "$AWS_REGION" 2>/dev/null || log_warning "Could not retrieve logs"
}

# Main function
main() {
    local command="$1"
    shift || true
    
    case "$command" in
        "clone"|"setup")
            check_dependencies
            clone_repo_if_needed
            setup_terraform_backend
            log_success "Repository and Terraform setup completed"
            ;;
        "show"|"status")
            check_dependencies
            clone_repo_if_needed
            setup_terraform_backend
            show_current_state
            ;;
        "backup")
            check_dependencies
            clone_repo_if_needed
            setup_terraform_backend
            backup_state
            ;;
        "restore")
            check_dependencies
            clone_repo_if_needed
            setup_terraform_backend
            restore_state "$1"
            ;;
        "aws"|"resources")
            check_dependencies
            show_aws_resources
            ;;
        "import")
            check_dependencies
            clone_repo_if_needed
            setup_terraform_backend
            import_existing_resources
            ;;
        "validate")
            check_dependencies
            clone_repo_if_needed
            setup_terraform_backend
            validate_state
            ;;
        "logs")
            check_dependencies
            show_logs "$1" "$2"
            ;;
        "help"|"")
            echo "Business Scraper State Management Script"
            echo "========================================"
            echo ""
            echo "Usage: $0 <command> [options]"
            echo ""
            echo "Commands:"
            echo "  clone|setup           Clone repository and setup Terraform"
            echo "  show|status           Show current Terraform state"
            echo "  backup                Backup current Terraform state"
            echo "  restore <file>        Restore Terraform state from backup"
            echo "  aws|resources         Show AWS resources status"
            echo "  import                Import existing AWS resources to Terraform"
            echo "  validate              Validate Terraform configuration and check drift"
            echo "  logs [function] [lines] Show Lambda function logs"
            echo "  help                  Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  REPO_URL              Repository URL to clone"
            echo "  PROJECT_DIR           Directory name for the project"
            echo "  AWS_REGION            AWS region"
            echo "  ENVIRONMENT           Environment name (dev/staging/prod)"
            echo "  TERRAFORM_BACKEND_BUCKET  S3 bucket for Terraform state"
            echo "  TERRAFORM_BACKEND_KEY     S3 key for Terraform state"
            echo "  STATE_BACKUP_DIR      Directory for state backups"
            echo ""
            echo "Examples:"
            echo "  $0 setup              # Initial setup"
            echo "  $0 show               # Show current state"
            echo "  $0 backup             # Backup state"
            echo "  $0 aws                # Show AWS resources"
            echo "  $0 logs               # Show recent logs"
            echo "  ENVIRONMENT=prod $0 show  # Show prod environment state"
            ;;
        *)
            log_error "Unknown command: $command"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"