#!/bin/bash

# =============================================================================
# AWS Credential Monitor Script
# =============================================================================
# Monitors AWS credentials and automatically refreshes them when expired
# Also restarts the backend container when credentials are refreshed
#
# Usage: ./scripts/aws-credential-monitor.sh
# Or run in background: ./scripts/aws-credential-monitor.sh &
#
# To stop: kill the process or press Ctrl+C
# =============================================================================

set -e

# Configuration
AWS_PROFILE="${AWS_PROFILE:-rnd}"
CHECK_INTERVAL="${CHECK_INTERVAL:-60}"  # seconds
DOCKER_COMPOSE_PATH="${DOCKER_COMPOSE_PATH:-docker-compose}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="${PROJECT_DIR}/logs/aws-credential-monitor.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Test AWS credentials
test_aws_credentials() {
    log "INFO" "${BLUE}Testing AWS credentials...${NC}"
    
    # Try to get caller identity (lightweight test)
    if aws sts get-caller-identity --profile "$AWS_PROFILE" >/dev/null 2>&1; then
        log "INFO" "${GREEN}✅ AWS credentials are valid${NC}"
        return 0
    else
        log "WARN" "${YELLOW}❌ AWS credentials test failed${NC}"
        return 1
    fi
}

# Test S3 bucket access specifically
test_s3_access() {
    local bucket_name="devops-hackathon-bucket-sysaid"
    local region="eu-west-1"
    
    log "INFO" "${BLUE}Testing S3 bucket access...${NC}"
    
    if aws s3 ls "s3://$bucket_name" --region "$region" --profile "$AWS_PROFILE" >/dev/null 2>&1; then
        log "INFO" "${GREEN}✅ S3 bucket access is working${NC}"
        return 0
    else
        log "WARN" "${YELLOW}❌ S3 bucket access failed${NC}"
        return 1
    fi
}

# Refresh AWS credentials
refresh_aws_credentials() {
    log "INFO" "${YELLOW}🔄 Refreshing AWS credentials...${NC}"
    
    # Run AWS SSO login
    if aws sso login --profile "$AWS_PROFILE"; then
        log "INFO" "${GREEN}✅ AWS SSO login successful${NC}"
        return 0
    else
        log "ERROR" "${RED}❌ AWS SSO login failed${NC}"
        return 1
    fi
}

# Restart backend container
restart_backend() {
    log "INFO" "${YELLOW}🔄 Restarting backend container...${NC}"
    
    cd "$PROJECT_DIR"
    
    if $DOCKER_COMPOSE_PATH restart backend; then
        log "INFO" "${GREEN}✅ Backend container restarted successfully${NC}"
        return 0
    else
        log "ERROR" "${RED}❌ Failed to restart backend container${NC}"
        return 1
    fi
}

# Test health endpoint
test_health_endpoint() {
    log "INFO" "${BLUE}Testing health endpoint...${NC}"
    
    # Wait a moment for container to be ready
    sleep 5
    
    local health_response
    if health_response=$(curl -s "http://localhost:8000/health" 2>/dev/null); then
        local s3_status
        s3_status=$(echo "$health_response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['services']['s3'])" 2>/dev/null || echo "unknown")
        
        if [ "$s3_status" = "available" ]; then
            log "INFO" "${GREEN}✅ Health endpoint shows S3 is available${NC}"
            return 0
        else
            log "WARN" "${YELLOW}⚠️  Health endpoint shows S3 status: $s3_status${NC}"
            return 1
        fi
    else
        log "ERROR" "${RED}❌ Failed to reach health endpoint${NC}"
        return 1
    fi
}

# Main monitoring loop
monitor_credentials() {
    log "INFO" "${GREEN}🚀 Starting AWS credential monitor${NC}"
    log "INFO" "Profile: $AWS_PROFILE"
    log "INFO" "Check interval: $CHECK_INTERVAL seconds"
    log "INFO" "Project directory: $PROJECT_DIR"
    log "INFO" "Log file: $LOG_FILE"
    log "INFO" "Press Ctrl+C to stop"
    echo ""
    
    local consecutive_failures=0
    local max_failures=3
    
    while true; do
        log "INFO" "${BLUE}--- Credential Check Cycle ---${NC}"
        
        # Test AWS credentials
        if test_aws_credentials && test_s3_access; then
            consecutive_failures=0
            
            # Also test the health endpoint
            if ! test_health_endpoint; then
                log "WARN" "${YELLOW}Health endpoint indicates issues, but AWS CLI works. Might need container restart.${NC}"
                if restart_backend; then
                    test_health_endpoint
                fi
            fi
        else
            consecutive_failures=$((consecutive_failures + 1))
            log "WARN" "${YELLOW}Consecutive failures: $consecutive_failures/$max_failures${NC}"
            
            if [ $consecutive_failures -ge $max_failures ]; then
                log "ERROR" "${RED}Too many consecutive failures. Attempting credential refresh...${NC}"
                
                if refresh_aws_credentials; then
                    log "INFO" "${GREEN}Credentials refreshed. Restarting backend...${NC}"
                    
                    if restart_backend; then
                        log "INFO" "${GREEN}Testing services after refresh...${NC}"
                        sleep 5
                        
                        if test_aws_credentials && test_s3_access && test_health_endpoint; then
                            log "INFO" "${GREEN}🎉 All services are now working!${NC}"
                            consecutive_failures=0
                        else
                            log "ERROR" "${RED}Services still not working after refresh${NC}"
                        fi
                    else
                        log "ERROR" "${RED}Failed to restart backend after credential refresh${NC}"
                    fi
                else
                    log "ERROR" "${RED}Failed to refresh credentials${NC}"
                fi
            fi
        fi
        
        log "INFO" "${BLUE}💤 Sleeping for $CHECK_INTERVAL seconds...${NC}"
        echo ""
        sleep "$CHECK_INTERVAL"
    done
}

# Signal handlers
cleanup() {
    log "INFO" "${YELLOW}🛑 Received interrupt signal. Shutting down monitor...${NC}"
    exit 0
}

# Trap signals
trap cleanup SIGINT SIGTERM

# Check prerequisites
check_prerequisites() {
    local missing_tools=()
    
    # Check if aws CLI is available
    if ! command -v aws >/dev/null 2>&1; then
        missing_tools+=("aws")
    fi
    
    # Check if docker-compose is available
    if ! command -v "$DOCKER_COMPOSE_PATH" >/dev/null 2>&1; then
        missing_tools+=("docker-compose")
    fi
    
    # Check if curl is available
    if ! command -v curl >/dev/null 2>&1; then
        missing_tools+=("curl")
    fi
    
    # Check if python3 is available
    if ! command -v python3 >/dev/null 2>&1; then
        missing_tools+=("python3")
    fi
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log "ERROR" "${RED}Missing required tools: ${missing_tools[*]}${NC}"
        exit 1
    fi
    
    # Check if we're in the right directory
    if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
        log "ERROR" "${RED}docker-compose.yml not found in $PROJECT_DIR${NC}"
        log "ERROR" "Please run this script from your project root directory"
        exit 1
    fi
    
    log "INFO" "${GREEN}✅ All prerequisites met${NC}"
}

# Main execution
main() {
    echo "================================================================================"
    echo "                       AWS Credential Monitor"
    echo "================================================================================"
    echo ""
    
    check_prerequisites
    
    # Run one initial test
    log "INFO" "${BLUE}Running initial credential test...${NC}"
    if test_aws_credentials && test_s3_access; then
        log "INFO" "${GREEN}✅ Initial tests passed. Starting monitor...${NC}"
    else
        log "WARN" "${YELLOW}⚠️  Initial tests failed. Monitor will attempt to fix...${NC}"
    fi
    
    echo ""
    monitor_credentials
}

# Show help
show_help() {
    cat << EOF
AWS Credential Monitor Script

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -p, --profile PROFILE   AWS profile to use (default: rnd)
    -i, --interval SECONDS  Check interval in seconds (default: 60)
    -d, --docker-compose PATH  Path to docker-compose (default: docker-compose)

EXAMPLES:
    # Run with defaults
    $0

    # Run with custom profile and interval
    $0 --profile myprofile --interval 30

    # Run in background
    $0 &

    # Run with custom docker-compose path
    $0 --docker-compose "docker compose"

ENVIRONMENT VARIABLES:
    AWS_PROFILE              AWS profile to use
    CHECK_INTERVAL           Check interval in seconds
    DOCKER_COMPOSE_PATH      Path to docker-compose command

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -p|--profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        -i|--interval)
            CHECK_INTERVAL="$2"
            shift 2
            ;;
        -d|--docker-compose)
            DOCKER_COMPOSE_PATH="$2"
            shift 2
            ;;
        *)
            log "ERROR" "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Run main function
main 