#!/bin/bash

# Simple AWS Credential Check Script
# Runs every 1 minute, tests AWS CLI, and refreshes credentials if needed

set -e

# Configuration
AWS_PROFILE="${AWS_PROFILE:-rnd}"
CHECK_INTERVAL=60  # 1 minute

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging function
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Test AWS credentials with a simple command
test_aws() {
    aws sts get-caller-identity --profile "$AWS_PROFILE" >/dev/null 2>&1
}

# Refresh credentials and restart backend
refresh_and_restart() {
    log "${YELLOW}AWS CLI failed. Running refresh commands...${NC}"
    
    # Run AWS SSO login
    log "${YELLOW}Running: aws sso login --profile $AWS_PROFILE${NC}"
    aws sso login --profile "$AWS_PROFILE"
    
    # Restart backend container
    log "${YELLOW}Running: docker-compose restart backend${NC}"
    docker-compose restart backend
    
    log "${GREEN}✅ Refresh complete${NC}"
}

# Main monitoring loop
main() {
    log "${GREEN}🚀 Starting simple AWS credential monitor (1-minute intervals)${NC}"
    log "Profile: $AWS_PROFILE"
    log "Press Ctrl+C to stop"
    echo ""
    
    while true; do
        if test_aws; then
            log "${GREEN}✅ AWS credentials OK${NC}"
        else
            log "${RED}❌ AWS credentials failed${NC}"
            refresh_and_restart
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Signal handler for clean exit
cleanup() {
    log "${YELLOW}🛑 Stopping monitor...${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Run the monitor
main 