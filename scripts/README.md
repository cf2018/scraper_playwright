# Business Scraper Deployment Scripts

This directory contains scripts for deploying and managing the Business Scraper Lambda function.

## Scripts Overview

### 1. `deploy.sh` - Complete Deployment Pipeline
Handles the full deployment process from repository cloning to Lambda deployment.

**Features:**
- Repository cloning/updating
- Terraform infrastructure deployment
- Docker image building and pushing to ECR
- Lambda function updates
- Deployment testing and validation

**Usage:**
```bash
# Full deployment
./scripts/deploy.sh

# Deploy with custom environment
ENVIRONMENT=prod AWS_REGION=us-west-2 ./scripts/deploy.sh

# Plan only (don't apply changes)
./scripts/deploy.sh --plan-only

# Skip repository cloning
./scripts/deploy.sh --skip-repo-clone

# Skip infrastructure deployment
./scripts/deploy.sh --skip-infrastructure

# Skip Docker image build
./scripts/deploy.sh --skip-image-build
```

**Environment Variables:**
- `REPO_URL` - Repository URL to clone
- `PROJECT_DIR` - Directory name for the project  
- `AWS_REGION` - AWS region for deployment
- `ENVIRONMENT` - Environment name (dev/staging/prod)
- `TERRAFORM_BACKEND_BUCKET` - S3 bucket for Terraform state
- `TERRAFORM_BACKEND_KEY` - S3 key for Terraform state

### 2. `retrieve-state.sh` - State Management
Manages Terraform state, AWS resources, and deployment information.

**Features:**
- Repository setup and Terraform initialization
- State backup and restoration
- AWS resource discovery and status
- Resource import into Terraform
- Configuration validation and drift detection
- CloudWatch logs viewing

**Usage:**
```bash
# Initial setup
./scripts/retrieve-state.sh setup

# Show current state
./scripts/retrieve-state.sh show

# Backup current state
./scripts/retrieve-state.sh backup

# Restore from backup
./scripts/retrieve-state.sh restore ./terraform-backups/terraform_state_dev_latest.tfstate

# Show AWS resources
./scripts/retrieve-state.sh aws

# Import existing resources
./scripts/retrieve-state.sh import

# Validate configuration
./scripts/retrieve-state.sh validate

# View Lambda logs
./scripts/retrieve-state.sh logs
./scripts/retrieve-state.sh logs my-function-name 100
```

## Quick Start Guide

### First Time Deployment

1. **Configure AWS credentials:**
   ```bash
   aws configure
   # OR set environment variables
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=us-east-1
   ```

2. **Set up repository and infrastructure:**
   ```bash
   # Clone and setup
   ./scripts/retrieve-state.sh setup
   
   # Edit configuration
   nano scraper_playwright/infra/terraform.tfvars
   ```

3. **Deploy everything:**
   ```bash
   # Full deployment
   ./scripts/deploy.sh
   ```

### Existing Infrastructure

1. **Retrieve existing state:**
   ```bash
   # Setup and show current state
   ./scripts/retrieve-state.sh setup
   ./scripts/retrieve-state.sh show
   ```

2. **Import existing resources (if needed):**
   ```bash
   ./scripts/retrieve-state.sh import
   ```

3. **Update deployment:**
   ```bash
   # Update with latest code
   ./scripts/deploy.sh
   ```

## Environment-Specific Deployments

### Development Environment
```bash
ENVIRONMENT=dev ./scripts/deploy.sh
```

### Staging Environment
```bash
ENVIRONMENT=staging \
AWS_REGION=us-west-2 \
TERRAFORM_BACKEND_BUCKET=my-terraform-state \
./scripts/deploy.sh
```

### Production Environment
```bash
ENVIRONMENT=prod \
AWS_REGION=us-east-1 \
TERRAFORM_BACKEND_BUCKET=my-terraform-state-prod \
TERRAFORM_BACKEND_KEY=business-scraper/prod/terraform.tfstate \
./scripts/deploy.sh
```

## Troubleshooting

### Common Issues

1. **AWS Credentials Not Found**
   ```bash
   aws configure
   # or
   export AWS_ACCESS_KEY_ID=...
   export AWS_SECRET_ACCESS_KEY=...
   ```

2. **Docker Daemon Not Running**
   ```bash
   sudo systemctl start docker
   # or
   sudo service docker start
   ```

3. **Terraform State Lock**
   ```bash
   # Force unlock (use carefully)
   cd scraper_playwright/infra
   terraform force-unlock LOCK_ID
   ```

4. **ECR Login Issues**
   ```bash
   # Manual ECR login
   aws ecr get-login-password --region us-east-1 | \
   docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
   ```

### Debugging

1. **View detailed logs:**
   ```bash
   ./scripts/retrieve-state.sh logs my-lambda-function 200
   ```

2. **Check AWS resources:**
   ```bash
   ./scripts/retrieve-state.sh aws
   ```

3. **Validate configuration:**
   ```bash
   ./scripts/retrieve-state.sh validate
   ```

4. **Check Terraform state:**
   ```bash
   ./scripts/retrieve-state.sh show
   ```

### Recovery Procedures

1. **Restore from backup:**
   ```bash
   # List available backups
   ls -la ./terraform-backups/
   
   # Restore specific backup
   ./scripts/retrieve-state.sh restore ./terraform-backups/terraform_state_prod_20241020_143022.tfstate
   ```

2. **Import existing resources:**
   ```bash
   ./scripts/retrieve-state.sh import
   ```

3. **Recreate infrastructure:**
   ```bash
   # Destroy and recreate (CAUTION!)
   cd scraper_playwright/infra
   terraform destroy
   cd ../..
   ./scripts/deploy.sh
   ```

## Security Considerations

- Store sensitive variables in `terraform.tfvars` (gitignored)
- Use AWS IAM roles with minimal required permissions
- Enable S3 backend encryption for Terraform state
- Regularly rotate AWS access keys
- Monitor CloudWatch logs for security events

## Cost Optimization

- Use smaller Lambda memory sizes if possible
- Set appropriate log retention periods
- Clean up unused ECR images
- Monitor AWS costs with billing alerts
- Use scheduled execution instead of API Gateway for batch processing