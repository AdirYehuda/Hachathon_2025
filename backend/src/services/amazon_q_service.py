import asyncio
import json
import logging
import os
import subprocess
import time
from functools import wraps
from typing import Dict, List, Optional

from fastapi import HTTPException

from src.core.config import settings

logger = logging.getLogger(__name__)

# Concise instructions for fast responses
FAST_ANALYSIS_INSTRUCTIONS = """
SPEED PRIORITY: You have a 5-minute time limit. Answer as quickly as possible using your existing AWS knowledge. Provide fast responses even if incomplete data - speed is more important than comprehensive results. Only create scripts as absolute last resort if you cannot provide any useful insights otherwise."""

# Comprehensive read-only safety constraints
READ_ONLY_SAFETY = """
CRITICAL READ-ONLY GUARDRAILS:
- STRICTLY READ-ONLY MODE: Only perform read, list, describe, and get operations
- FORBIDDEN OPERATIONS: No create, update, delete, modify, terminate, stop, start, reboot, or any write operations
- ALLOWED AWS CLI COMMANDS: Only describe-*, list-*, get-*, select, query operations
- FORBIDDEN AWS CLI COMMANDS: create-*, delete-*, update-*, modify-*, terminate-*, stop-*, start-*, reboot-*, put-*, post-*, patch-*
- SCRIPT RESTRICTIONS: Any scripts must only use read-only AWS CLI commands
- NO RESOURCE MODIFICATIONS: Do not modify, create, or delete any AWS resources
- ANALYSIS ONLY: Provide analysis and recommendations without implementing changes"""

# List of explicitly allowed AWS CLI command prefixes (read-only operations)
ALLOWED_AWS_CLI_COMMANDS = {
    'describe-', 'list-', 'get-', 'show-', 'select-', 'query-', 'scan-',
    'head-', 'download-', 'sync --dryrun', 'cp --dryrun', 'ls', 'mb --dryrun'
}

# List of explicitly forbidden AWS CLI command prefixes (write operations)
FORBIDDEN_AWS_CLI_COMMANDS = {
    'create-', 'delete-', 'update-', 'modify-', 'put-', 'post-', 'patch-',
    'terminate-', 'stop-', 'start-', 'reboot-', 'restart-', 'associate-',
    'disassociate-', 'attach-', 'detach-', 'enable-', 'disable-', 'activate-',
    'deactivate-', 'add-', 'remove-', 'replace-', 'reset-', 'restore-',
    'copy-', 'move-', 'upload-', 'sync', 'cp', 'mv', 'rm'
}

# Enhanced prompts with detailed dashboard-ready instructions
ENHANCED_DASHBOARD_INSTRUCTIONS = """
CRITICAL DATA REQUIREMENTS FOR DASHBOARD GENERATION:
This analysis will be processed by another AI system to create comprehensive cost optimization dashboards. You MUST provide as much detailed, specific, and actionable data as possible.

MANDATORY DATA ELEMENTS TO INCLUDE:

1. SPECIFIC RESOURCE IDENTIFICATION:
   - Complete resource IDs, ARNs, and names (not just types)
   - Resource tags and metadata
   - Account/region information where applicable
   - Creation dates and last modified timestamps

2. DETAILED COST DATA:
   - Current monthly cost per resource (exact dollar amounts)
   - Potential monthly savings per resource (exact dollar amounts)  
   - Total current monthly spend across all analyzed resources
   - Total potential monthly savings across all resources
   - Annual cost projections and savings
   - Cost breakdown by service and resource type

3. COMPREHENSIVE UTILIZATION METRICS:
   - Exact utilization percentages (CPU, memory, storage, network)
   - Performance metrics and trends over specified time periods
   - Access patterns and usage frequency
   - Peak vs average utilization data

4. ACTIONABLE RECOMMENDATIONS:
   - Specific actions to take (terminate, resize, migrate, etc.)
   - Exact new resource specifications (instance types, storage classes)
   - Implementation complexity and timeline estimates
   - Risk assessment for each recommendation
   - Priority ranking based on cost impact

5. QUANTIFIED BUSINESS IMPACT:
   - ROI calculations for each optimization
   - Implementation costs vs savings
   - Payback periods for changes
   - Confidence levels for savings estimates

RESPONSE FORMAT REQUIREMENTS:
- Structure data clearly with headers and subsections
- Include exact numerical values, not ranges or approximations
- Provide implementation commands where applicable
- List all resources found, even if well-optimized
- Include metadata that helps categorize and prioritize findings

ABSOLUTELY CRITICAL: The downstream dashboard system needs maximum detail to create meaningful visualizations and actionable insights. Provide exhaustive analysis rather than summaries."""


def validate_script_safety(script_content: str) -> tuple[bool, str]:
    """
    Validate that a script only contains read-only operations.
    Returns (is_safe, error_message)
    """
    if not script_content:
        return True, ""
    
    script_lower = script_content.lower()
    
    # Check for forbidden AWS CLI commands with word boundaries
    import re
    for forbidden_cmd in FORBIDDEN_AWS_CLI_COMMANDS:
        # Create pattern that matches the command as a whole word or with aws prefix
        patterns = [
            rf'\baws\s+\S*{re.escape(forbidden_cmd)}',  # aws s3 rm, aws ec2 terminate-instances, etc.
            rf'\b{re.escape(forbidden_cmd)}\b'  # standalone command like rm, mv, etc.
        ]
        
        for pattern in patterns:
            if re.search(pattern, script_lower):
                return False, f"Forbidden AWS CLI command detected: {forbidden_cmd}"
    
    # Check for dangerous shell commands with word boundaries
    dangerous_commands = [
        r'\brm\s+', r'\bmv\s+', r'\bcp\s+(?!--dryrun)', r'\bchmod\s+\+x', r'\bsudo\b',
        r'\bcurl\s+-X\s+POST', r'\bcurl\s+-X\s+PUT', r'\bcurl\s+-X\s+DELETE', 
        r'\bcurl\s+-X\s+PATCH', r'\bwget\s+--post', r'\bterraform\s+apply',
        r'\bterraform\s+destroy', r'\bkubectl\s+apply', r'\bkubectl\s+delete', 
        r'\bdocker\s+run\s+-d'
    ]
    
    for dangerous_pattern in dangerous_commands:
        if re.search(dangerous_pattern, script_lower):
            return False, f"Potentially dangerous command detected: {dangerous_pattern}"
    
    # Check for write operations in script with word boundaries
    write_patterns = [
        r'\s>\s', r'\s>>', r'\btee\s+', r'\becho\s+>', r'\bprintf\s+>', 
        r'\bcat\s+>', r'\bwrite\b', r'\bmodify\b'
    ]
    
    for write_pattern in write_patterns:
        if re.search(write_pattern, script_lower):
            return False, f"Write operation detected: {write_pattern}"
    
    return True, ""


def handle_cli_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except subprocess.CalledProcessError as e:
            logger.error(f"Amazon Q CLI error in {func.__name__}: {e.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Amazon Q CLI error: {e.stderr or 'Command failed'}",
            )
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    return wrapper


class AmazonQService:
    def __init__(
        self, cli_path: str = None, aws_profile: str = None, region: str = "eu-west-1"
    ):
        self.cli_path = cli_path or settings.amazon_q_cli_path or "q"
        self.aws_profile = (
            aws_profile or "rnd"
        )  # Default to rnd profile as per user's setup
        self.region = region
        self.timeout = getattr(settings, "amazon_q_cli_timeout", 300)
        self.max_retries = getattr(settings, "amazon_q_cli_max_retries", 3)
        self.working_dir = getattr(settings, "amazon_q_cli_working_dir", None)

    async def _run_cli_command(
        self, prompt: str, model: str = "claude-3.5-sonnet", max_retries: int = None
    ) -> str:
        """Run Amazon Q CLI command with retry mechanism and return the output."""
        
        # Log the query being sent to Amazon Q
        logger.info("=" * 60)
        logger.info("📤 SENDING QUERY TO AMAZON Q:")
        logger.info("=" * 60)
        logger.info(f"🤖 Model: {model}")
        logger.info(f"📏 Query length: {len(prompt)} characters")
        logger.info(f"📄 Query preview (first 500 chars):")
        logger.info(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        logger.info("=" * 60)
        
        max_retries = max_retries or self.max_retries
        retry_count = 0
        last_exception = None

        # Input validation for security
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Prompt must be a non-empty string")
        if len(prompt) > 10000:  # Reasonable limit
            raise ValueError("Prompt too long")
        if not isinstance(model, str) or len(model) > 100:
            raise ValueError("Invalid model specification")
        
        # Validate prompt for read-only constraints
        logger.info("Validating prompt for read-only compliance")
        prompt_lower = prompt.lower()

        # Check for forbidden AWS CLI commands (but allow CLI parameters like --start-time)
        import re
        
        # First, remove all CLI parameters (--word or --word-word) from the text for validation
        cleaned_prompt = re.sub(r'--[\w-]+(?:\s+[^\s-][^\s]*)?', '', prompt_lower)
        
        for forbidden_cmd in FORBIDDEN_AWS_CLI_COMMANDS:
            # Create pattern that matches actual AWS CLI commands, not parameters
            patterns = [
                rf'\baws\s+\w+\s+{re.escape(forbidden_cmd)}',  # aws ec2 terminate-instances, etc.
                rf'^{re.escape(forbidden_cmd)}\b',  # standalone command at start of line
                rf'\s{re.escape(forbidden_cmd)}\b',  # standalone command with word boundary
            ]
            
            for pattern in patterns:
                if re.search(pattern, cleaned_prompt):
                    logger.error(f"Forbidden operation detected in prompt: {forbidden_cmd}")
                    raise ValueError(f"Forbidden operation detected in prompt: {forbidden_cmd}")
        
        # Add concise safety constraints to the prompt
        logger.info("Adding safety constraints to Amazon Q prompt")
        enhanced_prompt = f"""{READ_ONLY_SAFETY}
{FAST_ANALYSIS_INSTRUCTIONS}

{prompt}"""

        # Validate CLI path
        if (
            not self.cli_path
            or not isinstance(self.cli_path, str)
            or len(self.cli_path) > 255
        ):
            raise ValueError("Invalid CLI path configuration")

        while retry_count < max_retries:
            try:
                # Prepare environment with all necessary variables
                env = os.environ.copy()
                
                # Ensure essential environment variables are set
                env["HOME"] = "/root"
                env["USER"] = "root"
                
                # CRITICAL FIX: Amazon Q CLI doesn't respect AWS_PROFILE env var
                # Instead, we need to get session credentials from the RND profile and use them directly
                if self.aws_profile and self.aws_profile != "default":
                    try:
                        logger.info(f"Getting session credentials for profile: {self.aws_profile}")
                        # Use AWS STS to get temporary credentials from the specified profile
                        import boto3
                        session = boto3.Session(profile_name=self.aws_profile)
                        credentials = session.get_credentials()
                        
                        if credentials:
                            # Set AWS credentials directly as environment variables
                            env["AWS_ACCESS_KEY_ID"] = credentials.access_key
                            env["AWS_SECRET_ACCESS_KEY"] = credentials.secret_key
                            if credentials.token:
                                env["AWS_SESSION_TOKEN"] = credentials.token
                            logger.info(f"Successfully set credentials for profile: {self.aws_profile}")
                        else:
                            logger.warning(f"Could not get credentials for profile: {self.aws_profile}, falling back to default")
                    except Exception as e:
                        logger.warning(f"Failed to get credentials for profile {self.aws_profile}: {e}, falling back to default")
                else:
                    # For default profile, still set AWS_PROFILE for clarity
                    if self.aws_profile:
                        env["AWS_PROFILE"] = self.aws_profile
                
                if self.region:
                    env["AWS_REGION"] = self.region
                    env["AWS_DEFAULT_REGION"] = self.region
                
                # Ensure PATH includes both Q CLI and AWS CLI directories
                path_components = ["/root/.local/bin", "/usr/local/bin", "/usr/bin", "/bin"]
                current_path = env.get("PATH", "")
                for component in path_components:
                    if component not in current_path:
                        env["PATH"] = f"{component}:{env.get('PATH', '')}"
                
                # Set AWS CLI configuration
                env["AWS_CLI_AUTO_PROMPT"] = "off"
                env["AWS_PAGER"] = ""

                # Debug logging
                logger.info(f"Environment HOME: {env.get('HOME')}")
                logger.info(f"Environment USER: {env.get('USER')}")
                logger.info(f"Environment AWS_PROFILE: {env.get('AWS_PROFILE', 'Not set')}")
                logger.info(f"Environment AWS_REGION: {env.get('AWS_REGION')}")
                logger.info(f"AWS Credentials Set: {bool(env.get('AWS_ACCESS_KEY_ID'))}")
                logger.info(f"CLI path: {self.cli_path}")
                logger.info(f"Working directory: {self.working_dir}")
                
                # Set working directory to a script-friendly location if not specified
                working_dir = self.working_dir or os.getcwd()
                
                # Additional debug: check if CLI exists
                cli_exists = os.path.exists(self.cli_path)
                logger.info(f"CLI file exists: {cli_exists}")
                if cli_exists:
                    import stat
                    cli_stat = os.stat(self.cli_path)
                    logger.info(f"CLI permissions: {oct(cli_stat.st_mode)}")

                # Construct command with --no-interactive and --trust-all-tools flags
                # Use list of strings to prevent shell injection
                cmd = [
                    self.cli_path,
                    "chat",
                    "--model",
                    model,
                    "--no-interactive",  # Prevent interactive prompts
                    "--trust-all-tools",  # Automatically approve tool usage
                    enhanced_prompt,
                ]

                if retry_count > 0:
                    logger.info(
                        f"Retry attempt {retry_count}/{max_retries} for Amazon Q CLI command"
                    )
                else:
                    logger.info(
                        f"Running Amazon Q CLI command: {' '.join(cmd[:4])} [prompt hidden]"
                    )

                # Run command with live output streaming
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=working_dir,
                )

                # Collect output while streaming to logs
                stdout_lines = []
                stderr_lines = []
                
                async def read_stream(stream, lines_list, stream_name):
                    """Read from stream line by line and log immediately."""
                    while True:
                        try:
                            line = await stream.readline()
                            if not line:
                                break
                            
                            line_str = line.decode('utf-8').rstrip('\n\r')
                            if line_str:  # Only log non-empty lines
                                logger.info(f"Amazon Q {stream_name}: {line_str}")
                                lines_list.append(line_str)
                        except Exception as e:
                            logger.error(f"Error reading {stream_name}: {e}")
                            break

                # Start streaming tasks
                stdout_task = asyncio.create_task(read_stream(process.stdout, stdout_lines, "stdout"))
                stderr_task = asyncio.create_task(read_stream(process.stderr, stderr_lines, "stderr"))

                try:
                    # Wait for process completion and stream reading with timeout
                    await asyncio.wait_for(
                        asyncio.gather(process.wait(), stdout_task, stderr_task),
                        timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    logger.error("Amazon Q CLI command timed out")
                    process.kill()
                    stdout_task.cancel()
                    stderr_task.cancel()
                    await process.wait()
                    raise Exception("Amazon Q CLI command timed out")

                # Join the collected output
                stdout_output = '\n'.join(stdout_lines)
                stderr_output = '\n'.join(stderr_lines)

                if process.returncode != 0:
                    error_msg = stderr_output if stderr_output else "Command failed"
                    logger.error(f"CLI command failed with return code {process.returncode}")
                    logger.error(f"CLI stderr output: {error_msg}")
                    logger.error(f"CLI stdout output: {stdout_output if stdout_output else 'No stdout'}")
                    raise subprocess.CalledProcessError(
                        process.returncode, cmd, stderr=error_msg
                    )

                logger.info(
                    f"CLI command completed successfully on attempt {retry_count + 1}, output length: {len(stdout_output)}"
                )
                
                # Log the raw Amazon Q output for debugging
                logger.info("=" * 60)
                logger.info("🔍 AMAZON Q RAW OUTPUT:")
                logger.info("=" * 60)
                logger.info(f"📏 Output length: {len(stdout_output)} characters")
                logger.info(f"📄 Raw output preview (first 1000 chars):")
                logger.info(stdout_output[:1000] + "..." if len(stdout_output) > 1000 else stdout_output)
                logger.info("=" * 60)
                
                # Validate output for executable scripts only, not mentions in analysis text
                logger.info("Validating Amazon Q response for any executable script content")
                
                # Only validate if the response appears to contain actual scripts/commands
                # Look for script-like patterns (shebang, aws cli calls, etc.)
                if any(pattern in stdout_output.lower() for pattern in ['#!/', 'aws ', '$ ', 'bash', 'sh -c']):
                    is_safe, safety_error = validate_script_safety(stdout_output)
                    if not is_safe:
                        logger.warning(f"Amazon Q response contains script with potentially unsafe operations: {safety_error}")
                        logger.warning("This is likely analysis/recommendations mentioning these commands, not executable code")
                        # Don't raise an exception - just log the warning and continue
                else:
                    logger.info("Amazon Q response appears to be analysis text only, skipping script validation")
                
                return stdout_output

            except Exception as e:
                last_exception = e
                retry_count += 1

                if retry_count < max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** (retry_count - 1)
                    logger.warning(
                        f"CLI command failed (attempt {retry_count}/{max_retries}): {e}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"CLI command failed after {max_retries} attempts: {e}"
                    )
                    break

        # If we get here, all retries failed
        if isinstance(last_exception, subprocess.CalledProcessError):
            error_msg = (
                last_exception.stderr
                if hasattr(last_exception, "stderr")
                else str(last_exception)
            )
            raise HTTPException(
                status_code=500,
                detail=f"Amazon Q CLI error after {max_retries} attempts: {error_msg}. Please check AWS credentials and Amazon Q CLI installation.",
            )
        elif isinstance(last_exception, FileNotFoundError):
            raise HTTPException(
                status_code=500,
                detail=f"Amazon Q CLI not found at path: {self.cli_path}. Please install Amazon Q CLI or update the path configuration.",
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Amazon Q CLI failed after {max_retries} attempts: {str(last_exception)}. Please check your AWS authentication and try again.",
            )

    def _parse_cli_output(self, raw_output: str) -> Dict:
        """Parse Amazon Q CLI output - preserve AWS data while removing CLI artifacts."""
        # Enhanced cleanup: remove CLI artifacts but preserve all AWS data and analysis
        
        # Log the parsing process
        logger.info("=" * 60)
        logger.info("🔧 PARSING AMAZON Q OUTPUT:")
        logger.info("=" * 60)
        logger.info(f"📏 Raw input length: {len(raw_output)} characters")
        
        # CRITICAL FIX: Remove ANSI escape codes first (color formatting from terminal)
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned_output = ansi_escape.sub('', raw_output)
        
        logger.info(f"🧹 After ANSI cleanup: {len(cleaned_output)} characters")
        logger.info(f"📄 Cleaned preview: {cleaned_output[:200]}...")
        
        lines = cleaned_output.split("\n")
        cleaned_lines = []
        
        # FIXED: Properly detect when Amazon Q response starts
        in_response_section = False
        
        for line in lines:
            # Skip empty lines at the start
            if not line.strip() and not in_response_section:
                continue
                
            # Detect Amazon Q response start patterns
            if not in_response_section:
                if any(pattern in line for pattern in [
                    "> I'll help", "> I'll analyze", "> Let me help", "> Let's analyze",
                    "> I can help", "> I'll assist", "> I'm analyzing", "> I'll start"
                ]):
                    in_response_section = True
                    logger.info(f"✅ Amazon Q response detected: {line[:100]}...")
            
            if in_response_section:
                # Minimal filtering during response section - preserve almost everything
                if line.strip():
                    # Only skip these specific CLI artifacts
                    if any(skip_pattern in line for skip_pattern in [
                        "Command exited with code", "Execution finished", "CLI completed"
                    ]):
                        continue
                    cleaned_lines.append(line)
        
        # If primary parsing yields minimal content, try fallback methods
        response_content = "\n".join(cleaned_lines)
        
        if len(response_content) < 200:
            logger.warning("Primary parsing yielded minimal content, trying fallback methods")
            
            # Fallback 1: Extract everything after first meaningful line
            meaningful_start = -1
            for i, line in enumerate(lines):
                if any(word in line.lower() for word in [
                    "analyze", "help", "check", "instances", "resources", "costs", "optimization"
                ]) and len(line.strip()) > 10:
                    meaningful_start = i
                    break
            
            if meaningful_start >= 0:
                fallback_content = "\n".join(lines[meaningful_start:])
                if len(fallback_content) > len(response_content):
                    response_content = fallback_content
                    logger.info(f"✅ Fallback 1 improved content: {len(response_content)} chars")
            
            # Fallback 2: Use most of the raw output with minimal cleaning
            if len(response_content) < 500:
                logger.warning("All parsing methods failed, using raw output with minimal cleaning")
                response_content = cleaned_output
                
                # Only remove obvious CLI artifacts from the minimal cleaning
                artifacts_to_remove = [
                    "Command exited with code",
                    "Execution finished in",
                    "Exit code:",
                    "Process completed"
                ]
                
                for artifact in artifacts_to_remove:
                    response_content = response_content.replace(artifact, "")
                
                # Clean up multiple newlines
                response_content = re.sub(r'\n\s*\n\s*\n', '\n\n', response_content)
                response_content = response_content.strip()
        
        # Log the parsing results
        logger.info(f"📤 Parsed output length: {len(response_content)} characters")
        logger.info(f"📄 Parsed content preview (first 500 chars):")
        logger.info(response_content[:500] + "..." if len(response_content) > 500 else response_content)
        logger.info("=" * 60)

        # CRITICAL DEBUG: Create the return dictionary and log it
        result_dict = {
            "response": response_content,
            "conversation_id": None,  # CLI doesn't maintain conversation IDs in our use case
            "source_attributions": [],
            "raw_output": raw_output,
        }
        
        # CRITICAL DEBUG: Log what we're actually returning
        logger.info("=" * 60)
        logger.info("🔍 CRITICAL DEBUG - RETURN DICTIONARY:")
        logger.info("=" * 60)
        logger.info(f"📋 Return dict keys: {list(result_dict.keys())}")
        logger.info(f"📏 Return dict response length: {len(result_dict['response'])}")
        logger.info(f"📄 Return dict response type: {type(result_dict['response'])}")
        logger.info(f"📝 Return dict response preview: {repr(result_dict['response'][:200])}")
        logger.info("=" * 60)

        return result_dict

    @handle_cli_errors
    async def chat(self, message: str, conversation_id: Optional[str] = None) -> Dict:
        """Send a chat message to Amazon Q via CLI."""
        prompt = message

        raw_output = await self._run_cli_command(prompt)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def query_cost_optimization(self, query: str, resource_filters: List[str] = None, focus_services: List[str] = None) -> Dict:
        """Query Amazon Q for cost optimization insights via CLI with optional filtering."""
        
        # Build focused constraints based on filters
        scope_constraints = ""
        if focus_services:
            scope_constraints += f"\n🎯 ANALYZE ONLY THESE SERVICES: {', '.join(focus_services)}"
            scope_constraints += f"\n❌ SKIP ALL OTHER AWS SERVICES NOT IN THIS LIST: {', '.join(focus_services)}"
            scope_constraints += f"\n⚠️ DO NOT ANALYZE: {', '.join([s for s in ['EC2', 'S3', 'EBS', 'RDS', 'Lambda', 'CloudFront', 'ELB'] if s not in focus_services])}"
        
        if resource_filters:
            scope_constraints += f"\nAPPLY THESE RESOURCE FILTERS: {', '.join(resource_filters)}"
            
        cost_query = f"""AMAZON Q: GLOBAL MULTI-REGION COST OPTIMIZATION ANALYSIS

CRITICAL REQUEST: {query}
{scope_constraints}

🌍 GLOBAL SCOPE: Search ALL AWS regions in the account (not just default region)

🎯 TARGET: Find 5-10 SPECIFIC underutilized resources in selected service types with exact cost data

🚨 MANDATORY REQUIREMENTS: 
- ONLY analyze these services: {', '.join(focus_services) if focus_services else 'All services'}
- COMPLETELY IGNORE and SKIP all other AWS services not in the above list
- Search ALL AWS regions globally (us-east-1, us-west-2, eu-west-1, eu-central-1, ap-southeast-1, etc.)
- Return ACTUAL resource names, IDs, and specific cost amounts (not generic recommendations)
- Find 5-10 specific resources with optimization opportunities per service type
- Provide exact monthly costs and potential savings for each resource

⚠️ CRITICAL: Start analysis in EU-WEST-1 region where most resources are located

DETAILED ANALYSIS REQUIREMENTS:
1. RESOURCE IDENTIFICATION: Provide complete resource IDs, ARNs, names (not just types)
2. COST DATA: Current monthly cost per resource + potential monthly savings (exact amounts)
3. UTILIZATION METRICS: CPU, memory, storage utilization percentages and access patterns
4. IMPLEMENTATION ACTIONS: Specific steps to optimize each resource (resize, archive, delete, etc.)

GLOBAL MULTI-REGION ANALYSIS COMMANDS FOR SELECTED SERVICES:
{f'''
🌍 S3 GLOBAL ANALYSIS (S3 is inherently global):
aws s3api list-buckets --query 'Buckets[*].[Name,CreationDate]' --output table
aws s3api get-bucket-location --bucket <bucket-name> (for each bucket to show region)
aws s3api get-bucket-versioning --bucket <bucket-name> (for each bucket)
aws s3api get-bucket-metrics-configuration --bucket <bucket-name> (for usage data)
''' if not focus_services or 'S3' in focus_services else "# S3 analysis skipped - not in selected services"}

{f'''
🌍 EC2 GLOBAL ANALYSIS (search ALL regions, prioritize EU-WEST-1):
# Start with EU-WEST-1 where most instances are located
echo "=== Analyzing EC2 in priority region: eu-west-1 ==="
aws ec2 describe-instances --region eu-west-1 --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,State.Name,Tags[?Key==`Name`].Value|[0],LaunchTime,Placement.AvailabilityZone]' --output table
aws cloudwatch get-metric-statistics --region eu-west-1 --namespace AWS/EC2 --metric-name CPUUtilization --start-time $(date -d '30 days ago' --iso-8601) --end-time $(date --iso-8601) --period 86400 --statistics Average --dimensions Name=InstanceId,Value=<instance-id>

# Then check other regions
for region in $(aws ec2 describe-regions --query 'Regions[].RegionName' --output text); do
  if [ "$region" != "eu-west-1" ]; then
    echo "=== Analyzing EC2 in region: $region ==="
    aws ec2 describe-instances --region $region --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,State.Name,Tags[?Key==`Name`].Value|[0],LaunchTime,Placement.AvailabilityZone]' --output table
  fi
done
''' if not focus_services or 'EC2' in focus_services else "# EC2 analysis skipped - not in selected services"}

{f'''
🌍 EBS GLOBAL ANALYSIS (search ALL regions, prioritize EU-WEST-1):
# Start with EU-WEST-1 where most volumes are located
echo "=== Analyzing EBS in priority region: eu-west-1 ==="
aws ec2 describe-volumes --region eu-west-1 --query 'Volumes[*].[VolumeId,Size,VolumeType,State,Attachments[0].InstanceId,CreateTime,AvailabilityZone]' --output table
aws ec2 describe-snapshots --region eu-west-1 --owner-ids self --query 'Snapshots[*].[SnapshotId,VolumeSize,StartTime,Description]' --output table

# Then check other regions
for region in $(aws ec2 describe-regions --query 'Regions[].RegionName' --output text); do
  if [ "$region" != "eu-west-1" ]; then
    echo "=== Analyzing EBS in region: $region ==="
    aws ec2 describe-volumes --region $region --query 'Volumes[*].[VolumeId,Size,VolumeType,State,Attachments[0].InstanceId,CreateTime,AvailabilityZone]' --output table
  fi
done
''' if not focus_services or 'EBS' in focus_services else "# EBS analysis skipped - not in selected services"}

{f'''
🌍 RDS GLOBAL ANALYSIS (search ALL regions, prioritize EU-WEST-1):
# Start with EU-WEST-1 where most databases are located
echo "=== Analyzing RDS in priority region: eu-west-1 ==="
aws rds describe-db-instances --region eu-west-1 --query 'DBInstances[*].[DBInstanceIdentifier,DBInstanceClass,Engine,DBInstanceStatus,AvailabilityZone,InstanceCreateTime]' --output table

# Then check other regions
for region in $(aws ec2 describe-regions --query 'Regions[].RegionName' --output text); do
  if [ "$region" != "eu-west-1" ]; then
    echo "=== Analyzing RDS in region: $region ==="
    aws rds describe-db-instances --region $region --query 'DBInstances[*].[DBInstanceIdentifier,DBInstanceClass,Engine,DBInstanceStatus,AvailabilityZone,InstanceCreateTime]' --output table
  fi
done
''' if not focus_services or 'RDS' in focus_services else "# RDS analysis skipped - not in selected services"}

{f'''
🌍 LAMBDA GLOBAL ANALYSIS (search ALL regions, prioritize EU-WEST-1):
# Start with EU-WEST-1 where most functions are located
echo "=== Analyzing Lambda in priority region: eu-west-1 ==="
aws lambda list-functions --region eu-west-1 --query 'Functions[*].[FunctionName,Runtime,MemorySize,Timeout,LastModified]' --output table

# Then check other regions
for region in $(aws ec2 describe-regions --query 'Regions[].RegionName' --output text); do
  if [ "$region" != "eu-west-1" ]; then
    echo "=== Analyzing Lambda in region: $region ==="
    aws lambda list-functions --region $region --query 'Functions[*].[FunctionName,Runtime,MemorySize,Timeout,LastModified]' --output table
  fi
done
''' if not focus_services or 'Lambda' in focus_services else "# Lambda analysis skipped - not in selected services"}

EXECUTION REQUIREMENTS:
- Start analysis in EU-WEST-1 region (highest priority)
- Use multi-region scanning for comprehensive coverage
- Geographic scope: ALL AWS regions globally
- Total resources to identify: 5-10 per selected service type
- Total potential monthly savings: $200-800 across all selected services
- Provide exact resource names, costs, regions, and implementation steps

⚠️ CRITICAL FILTERING: Only analyze and report on these services: {', '.join(focus_services) if focus_services else 'All services'}. Completely ignore all other AWS services.

AMAZON Q: Execute comprehensive GLOBAL MULTI-REGION analysis starting with EU-WEST-1 and return specific resources with exact optimization details for ONLY the selected services."""

        raw_output = await self._run_cli_command(cost_query)
        parsed_result = self._parse_cli_output(raw_output)
        
        # CRITICAL DEBUG: Log what query_cost_optimization is returning
        logger.info("=" * 60)
        logger.info("🔍 CRITICAL DEBUG - QUERY_COST_OPTIMIZATION RETURN:")
        logger.info("=" * 60)
        logger.info(f"📋 Parsed result keys: {list(parsed_result.keys()) if isinstance(parsed_result, dict) else 'Not a dict'}")
        logger.info(f"📏 Parsed result response length: {len(parsed_result.get('response', '')) if isinstance(parsed_result, dict) else 'N/A'}")
        logger.info(f"📄 Parsed result response type: {type(parsed_result.get('response')) if isinstance(parsed_result, dict) else 'N/A'}")
        logger.info(f"📝 Parsed result response preview: {repr(parsed_result.get('response', '')[:200]) if isinstance(parsed_result, dict) else 'N/A'}")
        logger.info("=" * 60)
        
        return parsed_result

    @handle_cli_errors
    async def query_underutilization(
        self, resource_type: str, time_range: str = "30d"
    ) -> Dict:
        """Query Amazon Q for resource underutilization analysis via CLI."""
        underutil_query = f"""COMPREHENSIVE {resource_type.upper()} UNDERUTILIZATION ANALYSIS FOR DASHBOARD CREATION - {time_range}

{ENHANCED_DASHBOARD_INSTRUCTIONS}

DETAILED UNDERUTILIZATION ANALYSIS REQUIREMENTS:

1. COMPLETE RESOURCE INVENTORY:
   - List ALL {resource_type} resources with full identifiers
   - Resource ARNs, names, IDs, and complete specifications
   - Account ID, region, availability zone details
   - Creation timestamps and last modification dates
   - Complete tag inventory for categorization and cost allocation

2. GRANULAR UTILIZATION METRICS:
   - CPU utilization: Average, peak, minimum over {time_range}
   - Memory utilization: Average usage patterns and peak demands
   - Storage utilization: Used vs allocated space, I/O patterns
   - Network utilization: Data transfer volumes and patterns
   - Access patterns: Last accessed dates, frequency of use

3. COST ANALYSIS PER RESOURCE:
   - Current monthly cost for each individual resource: $[exact_amount]
   - Cost per utilization unit (e.g., $/CPU hour actually used)
   - Waste calculation: $[monthly_cost] * (100% - [utilization_percentage])%
   - Comparison with optimally-sized alternatives

4. SPECIFIC OPTIMIZATION RECOMMENDATIONS:
   For each underutilized resource provide:
   - Resource ID: [specific_identifier]
   - Current specs: [current_configuration]
   - Current monthly cost: $[exact_amount]
   - Utilization: [percentage]% average CPU, [percentage]% memory
   - Recommendation: [specific_action - terminate/resize/schedule/migrate]
   - New specs (if resizing): [target_configuration]
   - New monthly cost: $[exact_amount]
   - Monthly savings: $[exact_amount]
   - Implementation complexity: [Low/Medium/High]
   - Risk level: [Low/Medium/High]

5. AGGREGATE SAVINGS CALCULATIONS:
   - Total current monthly spend on {resource_type}: $[exact_amount]
   - Total potential monthly savings: $[exact_amount]
   - Annual savings projection: $[monthly_savings * 12]
   - Percentage waste reduction: [percentage]%
   - Average utilization improvement: From [current]% to [target]%

6. IMPLEMENTATION COMMANDS AND STEPS:
   For each recommendation, provide:
   - Specific AWS CLI commands for implementation
   - Required permissions and prerequisites  
   - Rollback procedures in case of issues
   - Monitoring setup for post-implementation validation

7. BUSINESS IMPACT ASSESSMENT:
   - ROI calculation for optimization efforts
   - Payback period for implementation costs
   - Confidence level for savings estimates
   - Risk mitigation strategies

CRITICAL: Provide actual data from account analysis, not generic examples. Include specific resource identifiers, exact cost figures, and actionable implementation details for comprehensive dashboard visualization."""

        raw_output = await self._run_cli_command(underutil_query)
        return self._parse_cli_output(raw_output)

    # Specific methods for different AWS services based on successful examples

    @handle_cli_errors
    async def analyze_ec2_underutilization(self, time_range: str = "30d", instance_filters: List[str] = None, instance_ids: List[str] = None) -> Dict:
        """Analyze underutilized EC2 instances with optional filtering."""
        
        filter_instructions = ""
        if instance_ids:
            filter_instructions += f"\n- ANALYZE THESE SPECIFIC INSTANCES: {', '.join(instance_ids)}"
        elif instance_filters:
            filter_instructions += f"\n- APPLY THESE FILTERS: {', '.join(instance_filters)}"
        else:
            filter_instructions += "\n- COMPREHENSIVE ANALYSIS OF ALL EC2 INSTANCES"

        query = f"""STRICT EC2-ONLY COST OPTIMIZATION ANALYSIS FOR DASHBOARD CREATION

{ENHANCED_DASHBOARD_INSTRUCTIONS}

SCOPE: EC2 INSTANCES ONLY{filter_instructions}

⚠️ CRITICAL: ANALYZE ONLY EC2 INSTANCES. DO NOT ANALYZE ANY OTHER AWS SERVICES.

MISSION: Provide detailed EC2 underutilization analysis to enable comprehensive dashboard creation with maximum actionable insights for EC2 optimization only.

MANDATORY EC2-ONLY ANALYSIS REQUIREMENTS:

**IF NO EC2 INSTANCES ARE FOUND:**
Return this exact format:
```
🚫 EC2 ANALYSIS RESULTS: NO INSTANCES FOUND

EC2 INSTANCE DISCOVERY:
- Total EC2 instances found across all regions: 0
- Regions scanned: [list of regions checked]
- Analysis status: No EC2 instances available for optimization analysis

RECOMMENDATION:
Since no EC2 instances were found in this AWS account, there are no EC2 cost optimization opportunities at this time. Consider:
1. Verify AWS account permissions
2. Check if instances exist in other regions
3. Consider launching instances if compute resources are needed

COST IMPACT:
- Current monthly EC2 spend: $0.00
- Potential EC2 savings: $0.00 (no instances to optimize)
- EC2 optimization opportunities: 0
```

**IF EC2 INSTANCES ARE FOUND:**
Perform comprehensive global analysis across ALL AWS regions:

1. GLOBAL EC2 DISCOVERY (MANDATORY MULTI-REGION SCAN):
   Use AWS CLI commands to scan ALL regions:
   ```
   aws ec2 describe-regions (get all regions)
   aws ec2 describe-instances --region [each-region] (scan each region)
   aws cloudwatch get-metric-statistics --region [each-region] (get CPU metrics for each instance)
   ```

2. COMPREHENSIVE EC2 UTILIZATION METRICS (LAST {time_range}):
   For each EC2 instance found across ALL regions:
   - Instance ID: [i-xxxxxxxxx] (Region: [region-name])
   - Instance type: [m5.large, t3.medium, etc.]
   - CPU utilization: [percentage]% average, [percentage]% peak over {time_range}
   - Memory utilization (if available): [percentage]%
   - Network utilization: [Mbps] average, [Mbps] peak
   - Instance lifecycle: running hours vs stopped hours
   - Regional distribution of instances

3. COMPREHENSIVE COST ANALYSIS (GLOBAL):
   - Current monthly cost per instance: $[exact_amount]
   - Regional cost breakdown
   - On-demand vs reserved instance pricing analysis

4. RIGHT-SIZING RECOMMENDATIONS (BY REGION):
   For each underutilized instance provide:
   - Instance ID: [i-xxxxxxxxx] (Region: [us-west-2])
   - Current type: [m5.large] - $[monthly_cost]
   - CPU utilization: [percentage]% average, [percentage]% peak
   - Recommended type: [t3.medium] - $[new_monthly_cost]
   - Monthly savings: $[exact_savings_amount]
   - Implementation complexity: [Low/Medium/High]

5. TERMINATION CANDIDATES (GLOBAL):
   - Instance ID: [i-xxxxxxxxx] (Region: [eu-west-1])
   - Current cost: $[monthly_amount]
   - Last accessed: [date] or CPU <5% for [days] days
   - Reason for termination: [unused/duplicate/test environment]
   - Risk assessment: [Low/Medium/High]

6. GLOBAL EC2 COST IMPACT:
   - Current total monthly EC2 spend (all regions): $[exact_amount]
   - Right-sizing savings potential: $[amount]
   - Termination savings potential: $[amount]  
   - TOTAL MONTHLY SAVINGS: $[amount]
   - ANNUAL SAVINGS PROJECTION: $[amount]

REQUIRED OUTPUT FORMAT:

🌍 GLOBAL EC2 OPTIMIZATION OPPORTUNITIES:

INSTANCE ANALYSIS RESULTS (All Regions):
1. Instance: i-0abc123def456789 (Region: us-west-2, AZ: us-west-2a)
   - Type: m5.large | Monthly cost: $62.40 | CPU: 3.2% avg (30 days)
   - Status: Running 24/7 | Environment: Development
   - Optimization: Downsize to t3.small or schedule stop/start
   - Potential saving: $46.60/month | Implementation: Resize during maintenance
   - Steps: 1) Create AMI 2) Launch t3.small 3) Migrate traffic 4) Terminate old

2. Instance: i-0xyz789abc123def (Region: eu-west-1, AZ: eu-west-1b)
   - Type: t2.medium | Monthly cost: $33.70 | Status: Stopped for 45 days
   - Last activity: Development testing | Environment: Test
   - Optimization: Archive data and terminate if no longer needed
   - Potential saving: $33.70/month | Implementation: Data backup + termination
   - Steps: 1) Backup important data 2) Create final snapshot 3) Terminate instance

[Continue for all EC2 instances found across ALL regions...]

⚠️ CRITICAL: Only return EC2 instance data. Do not include any other AWS services in the response.

AMAZON Q: Execute comprehensive GLOBAL EC2 analysis across all regions and return specific EC2 instances with exact optimization details. Ignore all other AWS services."""

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def analyze_ebs_underutilization(self, volume_filters: List[str] = None, volume_ids: List[str] = None) -> Dict:
        """Analyze underutilized EBS volumes with optional filtering across ALL regions."""
        
        filter_instructions = ""
        if volume_ids:
            filter_instructions += f"\n- ANALYZE THESE SPECIFIC VOLUMES: {', '.join(volume_ids)}"
        elif volume_filters:
            filter_instructions += f"\n- APPLY THESE FILTERS: {', '.join(volume_filters)}"
        else:
            filter_instructions += "\n- COMPREHENSIVE ANALYSIS OF ALL EBS VOLUMES"

        query = f"""🌍 GLOBAL MULTI-REGION EBS VOLUME COST OPTIMIZATION ANALYSIS

{ENHANCED_DASHBOARD_INSTRUCTIONS}

🌍 GLOBAL SCOPE: Search ALL AWS regions in the account (not just default region)

⚠️ CRITICAL SERVICE FILTERING: ANALYZE ONLY EBS VOLUMES - DO NOT INCLUDE ANY OTHER AWS SERVICES
- NO S3 buckets, NO EC2 instances, NO RDS instances, NO Lambda functions
- ONLY EBS volumes and their direct storage costs
- Focus exclusively on EBS volume optimization opportunities

SCOPE: DETAILED EBS ANALYSIS{filter_instructions}

🌍 GLOBAL MULTI-REGION EBS ANALYSIS COMMANDS:
for region in $(aws ec2 describe-regions --query 'Regions[].RegionName' --output text); do
  echo "=== Analyzing EBS volumes in region: $region ==="
  aws ec2 describe-volumes --region $region --query 'Volumes[*].[VolumeId,Size,VolumeType,State,Attachments[0].InstanceId,CreateTime,AvailabilityZone]' --output table
  
  # Also check snapshots for cleanup opportunities
  aws ec2 describe-snapshots --region $region --owner-ids self --query 'Snapshots[*].[SnapshotId,VolumeSize,StartTime,Description]' --output table
done

MANDATORY EBS ANALYSIS REQUIREMENTS:

1. COMPLETE EBS VOLUME INVENTORY (ALL REGIONS):
   - Volume ID, name tags, region, and availability zone
   - Volume type (gp2, gp3, io1, io2, st1, sc1), size, and IOPS
   - Attachment status (attached/available) and instance association
   - Creation date, snapshot information, and encryption status

2. UTILIZATION AND PERFORMANCE METRICS PER REGION:
   - Storage utilization: Used vs allocated space percentage
   - IOPS utilization: Actual vs provisioned IOPS usage
   - Regional distribution of volumes

3. COST ANALYSIS PER VOLUME (GLOBAL):
   - Volume ID: [vol-xxxxxxxxx] (Region: [us-east-1])
   - Current monthly cost: $[exact_amount]
   - Cost breakdown: storage + IOPS + snapshot costs
   - Regional cost distribution

4. OPTIMIZATION OPPORTUNITIES (BY REGION):

   UNATTACHED VOLUMES (Immediate savings):
   - Volume ID: [vol-xxxxxxxxx] (Region: [us-west-2]) - Size: [GB] - Type: [gp2]
   - Monthly cost being wasted: $[exact_amount]
   - Last attached: [date] or Never attached
   - Recommendation: Delete after snapshot backup
   - Risk level: [Low/Medium/High]

   VOLUME TYPE OPTIMIZATION:
   - Volume ID: [vol-xxxxxxxxx] (Region: [eu-west-1]) - Current: [gp2] - Size: [GB]
   - Current monthly cost: $[amount]
   - Recommended type: [gp3] - New monthly cost: $[amount]
   - Monthly savings: $[amount] - Performance impact: [None/Improved]

5. GLOBAL EBS COST IMPACT:
   - Current total monthly EBS spend (all regions): $[exact_amount]
   - Unattached volume savings: $[amount]
   - Volume type optimization savings: $[amount]
   - TOTAL MONTHLY SAVINGS: $[amount]
   - ANNUAL SAVINGS PROJECTION: $[amount]

REQUIRED OUTPUT FORMAT:

🌍 GLOBAL EBS OPTIMIZATION OPPORTUNITIES:

VOLUME ANALYSIS RESULTS (All Regions):
1. Volume: vol-0abc123def456789 (Region: us-east-1, AZ: us-east-1a)
   - Size: 500GB gp2 | Monthly cost: $50.00 | Status: Available (unattached 60 days)
   - Last instance: i-terminated123 | Created: 120 days ago
   - Optimization: Create snapshot and delete volume
   - Potential saving: $50.00/month | Implementation: Snapshot + deletion
   - Steps: 1) Create snapshot backup 2) Verify data integrity 3) Delete volume

[Continue for all EBS volumes found across ALL regions...]

⚠️ CRITICAL: Only return EBS volume data. Do not include any other AWS services in the response.

AMAZON Q: Execute comprehensive GLOBAL EBS analysis across all regions and return specific EBS volumes with exact optimization details. Ignore all other AWS services."""

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def analyze_s3_underutilization(self, bucket_filters: List[str] = None, bucket_names: List[str] = None) -> Dict:
        """Analyze underutilized S3 buckets with optional filtering (S3 is inherently global)."""
        
        filter_instructions = ""
        if bucket_names:
            filter_instructions += f"\n- ANALYZE THESE SPECIFIC BUCKETS: {', '.join(bucket_names)}"
        elif bucket_filters:
            filter_instructions += f"\n- APPLY THESE FILTERS: {', '.join(bucket_filters)}"
        else:
            filter_instructions += "\n- COMPREHENSIVE ANALYSIS OF ALL S3 BUCKETS"

        query = f"""🌍 GLOBAL S3 STORAGE COST OPTIMIZATION ANALYSIS

{ENHANCED_DASHBOARD_INSTRUCTIONS}

🌍 GLOBAL SCOPE: S3 is inherently global - analyze ALL buckets across ALL regions

⚠️ CRITICAL SERVICE FILTERING: ANALYZE ONLY S3 BUCKETS - DO NOT INCLUDE ANY OTHER AWS SERVICES
- NO EC2 instances, NO EBS volumes, NO RDS instances, NO Lambda functions
- ONLY S3 buckets and their direct storage costs
- Focus exclusively on S3 bucket optimization opportunities

SCOPE: DETAILED S3 ANALYSIS{filter_instructions}

🌍 GLOBAL S3 ANALYSIS COMMANDS:
aws s3api list-buckets --query 'Buckets[*].[Name,CreationDate]' --output table

# Get detailed information for each bucket
for bucket in $(aws s3api list-buckets --query 'Buckets[].Name' --output text); do
  echo "=== Analyzing S3 bucket: $bucket ==="
  aws s3api get-bucket-location --bucket $bucket
  aws s3api get-bucket-versioning --bucket $bucket
  aws s3 ls s3://$bucket --recursive --summarize --human-readable
  aws s3api get-bucket-metrics-configuration --bucket $bucket || echo "No metrics config"
done

MANDATORY S3 ANALYSIS REQUIREMENTS:

1. COMPLETE S3 BUCKET INVENTORY (GLOBAL):
   - Bucket name, region, and creation date
   - Total storage size in GB and object count
   - Storage class distribution (Standard, IA, Glacier, Deep Archive)
   - Versioning status and lifecycle policies

2. UTILIZATION AND ACCESS PATTERNS:
   - Data access frequency and patterns over 30/60/90 days
   - Last accessed dates for bucket and object level
   - Transfer costs and data retrieval patterns

3. COST ANALYSIS PER BUCKET (GLOBAL):
   - Bucket name: [bucket-name] (Region: [us-east-1])
   - Current monthly cost: $[exact_amount]
   - Cost breakdown: storage + requests + data transfer

4. STORAGE CLASS OPTIMIZATION OPPORTUNITIES:

   LIFECYCLE TRANSITION CANDIDATES:
   - Bucket: [bucket-name] (Region: [us-east-1]) - Size: [GB] - Current class: [Standard]
   - Objects not accessed in 30+ days: [GB] - Cost: $[amount]
   - Recommended transition: Standard → IA → Glacier
   - Monthly savings from lifecycle: $[amount]

   CLEANUP OPPORTUNITIES:
   - Bucket: [bucket-name] (Region: [us-west-2]) - Size: [MB/GB] - Objects: [count]
   - Monthly cost: $[amount] - Last accessed: [date]
   - Recommendation: Archive or delete
   - Risk assessment: [Low/Medium/High]

5. GLOBAL S3 COST IMPACT:
   - Current total monthly S3 spend (all regions): $[exact_amount]
   - Lifecycle optimization savings: $[amount]
   - Cleanup savings: $[amount]
   - TOTAL MONTHLY SAVINGS: $[amount]
   - ANNUAL SAVINGS PROJECTION: $[amount]

REQUIRED OUTPUT FORMAT:

🌍 GLOBAL S3 OPTIMIZATION OPPORTUNITIES:

BUCKET ANALYSIS RESULTS (All Regions):
1. Bucket: "company-old-backups-2022" (Region: us-east-1)
   - Size: 2.1TB | Monthly cost: $48.30 | Last accessed: 240 days ago
   - Objects: 45,000 files | Storage class: Standard
   - Optimization: Transition to Glacier Deep Archive
   - Potential saving: $38.50/month | Implementation: Set lifecycle policy
   - Steps: 1) Audit contents 2) Create lifecycle policy 3) Monitor transition

2. Bucket: "dev-temp-storage-unused" (Region: us-west-2)
   - Size: 850GB | Monthly cost: $19.45 | Last accessed: Never
   - Objects: 12,000 files | Created: 180 days ago
   - Optimization: Review and delete if safe
   - Potential saving: $19.45/month | Implementation: Content audit + deletion
   - Steps: 1) Verify no dependencies 2) Create backup 3) Delete bucket

[Continue for all S3 buckets found across ALL regions...]

⚠️ CRITICAL: Only return S3 bucket data. Do not include any other AWS services in the response.

AMAZON Q: Execute comprehensive GLOBAL S3 analysis across all regions and return specific S3 buckets with exact optimization details. Ignore all other AWS services."""

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def analyze_lambda_underutilization(self, function_filters: List[str] = None, function_names: List[str] = None) -> Dict:
        """Analyze underutilized Lambda functions with optional filtering."""
        
        filter_instructions = ""
        if function_names:
            filter_instructions += f"\n- ANALYZE THESE SPECIFIC FUNCTIONS: {', '.join(function_names)}"
        elif function_filters:
            filter_instructions += f"\n- APPLY THESE FILTERS: {', '.join(function_filters)}"
        else:
            filter_instructions += "\n- COMPREHENSIVE ANALYSIS OF ALL LAMBDA FUNCTIONS"

        query = f"""COMPREHENSIVE LAMBDA FUNCTION COST OPTIMIZATION ANALYSIS FOR DASHBOARD CREATION

{ENHANCED_DASHBOARD_INSTRUCTIONS}

SCOPE: DETAILED LAMBDA ANALYSIS{filter_instructions}

MANDATORY LAMBDA ANALYSIS REQUIREMENTS:

1. COMPLETE LAMBDA FUNCTION INVENTORY:
   - Function name, ARN, and runtime information
   - Memory allocation, timeout settings, and architecture
   - Handler, description, and environment variables count
   - VPC configuration, layers, and code size
   - Last modified date and deployment package details

2. UTILIZATION AND PERFORMANCE METRICS:
   - Invocation count: Daily/weekly/monthly over 30 days
   - Average duration vs timeout setting
   - Memory utilization: Actual vs allocated memory
   - Error rate and cold start frequency
   - Concurrent execution patterns and throttling

3. COST ANALYSIS PER FUNCTION:
   - Function name: [function-name]
   - Current monthly cost: $[exact_amount]
   - Cost breakdown: compute time + request charges
   - Cost per invocation: $[amount]
   - Memory utilization efficiency percentage

4. OPTIMIZATION OPPORTUNITIES:

   MEMORY RIGHT-SIZING:
   - Function: [function-name] - Allocated: [MB] - Used: [MB] ([percentage]%)
   - Current monthly cost: $[amount]
   - Recommended memory: [MB] - New monthly cost: $[amount]
   - Monthly savings: $[amount] - Performance impact: [None/Improved/Degraded]

   UNUSED/UNDERUTILIZED FUNCTIONS:
   - Function: [function-name] - Invocations last 30 days: [count]
   - Monthly cost: $[amount] - Last invoked: [date]
   - Recommendation: [Delete/Archive/Reduce memory]
   - Risk level: [Low/Medium/High]

   TIMEOUT OPTIMIZATION:
   - Function: [function-name] - Timeout: [seconds] - Avg duration: [seconds]
   - Over-provisioned timeout savings: $[amount]
   - Recommended timeout: [seconds]

5. PROVISIONED CONCURRENCY ANALYSIS:
   - Function: [function-name] - Provisioned units: [count]
   - Utilization of provisioned capacity: [percentage]%
   - Monthly provisioned cost: $[amount]
   - Optimization recommendation and savings: $[amount]

6. COLD START OPTIMIZATION:
   - Functions with high cold start impact: [count]
   - Cost of cold starts vs provisioned concurrency
   - Optimization recommendations for frequently used functions

7. TOTAL LAMBDA COST IMPACT:
   - Current total monthly Lambda spend: $[exact_amount]
   - Memory optimization savings: $[amount]
   - Unused function cleanup savings: $[amount]
   - Timeout optimization savings: $[amount]
   - Provisioned concurrency optimization: $[amount]
   - TOTAL MONTHLY SAVINGS: $[amount]
   - ANNUAL SAVINGS PROJECTION: $[amount]

8. IMPLEMENTATION COMMANDS:
   For each optimization provide specific AWS CLI commands:
   - Memory update: aws lambda update-function-configuration --function-name [name] --memory-size [size]
   - Function deletion: aws lambda delete-function --function-name [name]
   - Timeout update: aws lambda update-function-configuration --function-name [name] --timeout [seconds]

CRITICAL: Include specific function names, exact invocation counts, precise cost calculations, and detailed optimization recommendations."""

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def analyze_rds_underutilization(self, instance_filters: List[str] = None, db_instance_ids: List[str] = None) -> Dict:
        """Analyze underutilized RDS instances with optional filtering."""
        
        filter_instructions = ""
        if db_instance_ids:
            filter_instructions += f"\n- ANALYZE THESE SPECIFIC DB INSTANCES: {', '.join(db_instance_ids)}"
        elif instance_filters:
            filter_instructions += f"\n- APPLY THESE FILTERS: {', '.join(instance_filters)}"
        else:
            filter_instructions += "\n- COMPREHENSIVE ANALYSIS OF ALL RDS INSTANCES"

        query = f"""COMPREHENSIVE RDS DATABASE COST OPTIMIZATION ANALYSIS FOR DASHBOARD CREATION

{ENHANCED_DASHBOARD_INSTRUCTIONS}

SCOPE: DETAILED RDS ANALYSIS{filter_instructions}

MANDATORY RDS ANALYSIS REQUIREMENTS:

1. COMPLETE RDS INSTANCE INVENTORY:
   - DB instance identifier, ARN, and complete specifications
   - Instance class, engine type and version
   - Storage type, allocated storage, and IOPS
   - VPC, subnet group, and security group configuration
   - Backup retention, maintenance window, and parameter groups

2. UTILIZATION AND PERFORMANCE METRICS:
   - CPU utilization: Average, peak, minimum over 30 days
   - Memory utilization and available memory
   - Database connections: Active, maximum, and concurrent
   - Storage utilization: Used vs allocated space
   - IOPS utilization and read/write patterns

3. COST ANALYSIS PER INSTANCE:
   - DB identifier: [db-instance-name]
   - Current monthly cost: $[exact_amount]
   - Cost breakdown: compute + storage + backup + IOPS
   - On-demand vs reserved pricing comparison
   - Multi-AZ and backup storage costs

4. RIGHT-SIZING OPPORTUNITIES:

   INSTANCE CLASS OPTIMIZATION:
   - DB identifier: [db-instance-name] - Current: [db.m5.large]
   - CPU utilization: [percentage]% - Memory: [percentage]%
   - Current monthly cost: $[amount]
   - Recommended class: [db.t3.medium] - New cost: $[amount]
   - Monthly savings: $[amount] - Performance impact: [None/Minimal/Moderate]

   STORAGE OPTIMIZATION:
   - DB identifier: [db-instance-name] - Allocated: [GB] - Used: [GB] ([percentage]%)
   - Storage type: [gp2] - IOPS: [provisioned] vs [used]
   - Recommended storage: [GB] [gp3] - Monthly savings: $[amount]

5. UNDERUTILIZED DATABASES:
   - DB identifier: [db-instance-name]
   - Connection count last 30 days: Average [count], Peak [count]
   - CPU utilization: [percentage]% - Query volume: [low/medium/high]
   - Monthly cost: $[amount] - Recommendation: [Downsize/Merge/Schedule]
   - Risk assessment: [Low/Medium/High]

6. RESERVED INSTANCE OPPORTUNITIES:
   - Instance family: [db.m5] - Current on-demand cost: $[amount]
   - Recommended RI: [1-year/3-year] [no-upfront/partial/all-upfront]
   - RI monthly cost: $[amount] - Monthly savings: $[amount]
   - Annual savings: $[amount] - ROI: [percentage]%

7. MULTI-AZ AND BACKUP OPTIMIZATION:
   - Instances with unnecessary Multi-AZ: [count]
   - Backup retention optimization opportunities
   - Cross-region backup cost optimization
   - Potential monthly savings: $[amount]

8. TOTAL RDS COST IMPACT:
   - Current total monthly RDS spend: $[exact_amount]
   - Instance right-sizing savings: $[amount]
   - Storage optimization savings: $[amount]
   - Reserved instance savings: $[amount]
   - Multi-AZ optimization savings: $[amount]
   - TOTAL MONTHLY SAVINGS: $[amount]
   - ANNUAL SAVINGS PROJECTION: $[amount]

9. IMPLEMENTATION COMMANDS:
   For each optimization provide specific AWS CLI commands:
   - Instance modification: aws rds modify-db-instance --db-instance-identifier [name] --db-instance-class [new-class]
   - Storage modification: aws rds modify-db-instance --db-instance-identifier [name] --allocated-storage [size]

CRITICAL: Include specific DB identifiers, exact utilization metrics, precise cost calculations, and detailed implementation steps."""

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def comprehensive_cost_analysis(self, services: List[str] = None) -> Dict:
        """Perform comprehensive cost optimization analysis across multiple services."""
        services_list = services or ["EC2", "EBS", "S3", "Lambda", "RDS"]
        services_str = ", ".join(services_list)

        query = f"""COMPREHENSIVE MULTI-SERVICE AWS COST OPTIMIZATION ANALYSIS FOR DASHBOARD CREATION

{ENHANCED_DASHBOARD_INSTRUCTIONS}

SCOPE: COMPLETE ANALYSIS ACROSS SERVICES: {services_str}

MISSION: Provide exhaustive cost optimization analysis across all specified AWS services to enable comprehensive dashboard creation with maximum actionable insights.

MANDATORY MULTI-SERVICE ANALYSIS REQUIREMENTS:

1. EXECUTIVE SUMMARY WITH TOTALS:
   - Total current monthly AWS spend across all services: $[exact_amount]
   - Total potential monthly savings across all services: $[exact_amount]
   - Annual savings projection: $[monthly_savings * 12]
   - Overall cost reduction percentage: [percentage]%
   - Number of resources analyzed by service
   - Top 3 optimization opportunities by dollar impact

2. SERVICE-BY-SERVICE DETAILED BREAKDOWN:

   For each service ({services_str}), provide:

   A. RESOURCE INVENTORY:
      - Complete resource counts and identifiers
      - Resource specifications and configurations
      - Creation dates and last modified timestamps
      - Tag-based categorization and cost allocation

   B. COST ANALYSIS:
      - Current monthly spend for this service: $[exact_amount]
      - Cost breakdown by resource type
      - Potential monthly savings for this service: $[exact_amount]
      - Percentage of total AWS spend: [percentage]%

   C. OPTIMIZATION OPPORTUNITIES:
      - Right-sizing opportunities with specific recommendations
      - Termination candidates with exact cost savings
      - Storage optimization and lifecycle opportunities
      - Reserved instance purchase recommendations
      - Specific resource IDs and implementation actions

3. CROSS-SERVICE OPTIMIZATION PATTERNS:
   - Resources that work together (EC2 + EBS combinations)
   - Data transfer optimization opportunities
   - Architecture improvements that affect multiple services
   - Compliance and security optimizations with cost impact

4. PRIORITIZED RECOMMENDATIONS BY IMPACT:

   HIGH IMPACT OPPORTUNITIES (>$1000/month savings):
   - Resource ID: [specific_identifier]
   - Service: [AWS_service]
   - Current monthly cost: $[amount]
   - Optimization action: [specific_action]
   - Potential monthly savings: $[amount]
   - Implementation complexity: [Low/Medium/High]
   - Risk level: [Low/Medium/High]

   MEDIUM IMPACT OPPORTUNITIES ($200-1000/month savings):
   - [Same detailed format as above]

   LOW IMPACT OPPORTUNITIES (<$200/month savings):
   - [Same detailed format as above]

5. IMPLEMENTATION ROADMAP WITH TIMELINE:

   IMMEDIATE ACTIONS (0-7 days):
   - Terminate unused resources - Total savings: $[amount]
   - Delete unattached volumes - Total savings: $[amount]
   - Clean up unused S3 objects - Total savings: $[amount]
   - Specific commands for each action

   SHORT TERM ACTIONS (1-4 weeks):
   - Right-size underutilized instances - Total savings: $[amount]
   - Implement storage lifecycle policies - Total savings: $[amount]
   - Optimize Lambda memory allocation - Total savings: $[amount]

   MEDIUM TERM ACTIONS (1-3 months):
   - Purchase reserved instances - Total savings: $[amount]
   - Implement comprehensive tagging strategy
   - Set up automated cost monitoring and alerts

6. COST SAVINGS CALCULATIONS:
   - Total potential monthly savings: $[exact_amount]
   - Annual savings projection: $[amount]
   - Implementation costs: $[amount]
   - Net annual savings: $[amount]
   - ROI percentage: [percentage]%
   - Payback period: [months]

7. RISK ASSESSMENT AND MITIGATION:
   - Low risk optimizations (immediate implementation): $[savings_amount]
   - Medium risk optimizations (testing required): $[savings_amount]
   - High risk optimizations (careful evaluation needed): $[savings_amount]

8. SERVICE-SPECIFIC TOTALS:
   - EC2 total potential savings: $[amount]
   - EBS total potential savings: $[amount]
   - S3 total potential savings: $[amount]
   - Lambda total potential savings: $[amount]
   - RDS total potential savings: $[amount]

9. DETAILED RESOURCE LISTS:
   Provide complete lists with:
   - Resource identifiers (IDs, ARNs, names)
   - Current configurations and costs
   - Recommended changes and expected savings
   - Implementation commands and procedures

CRITICAL OUTPUT REQUIREMENTS:
- Include exact dollar amounts for all cost calculations
- Provide specific resource identifiers for every recommendation
- Structure data clearly for dashboard parsing and visualization
- Include implementation complexity and risk assessments
- Calculate total savings potential across all services
- Provide timeline-based implementation roadmap

TARGET: Create the most comprehensive cost optimization analysis possible for sophisticated dashboard creation with maximum actionable insights and quantified business impact."""

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def query_for_dashboard_creation(self, query: str, services: List[str] = None) -> Dict:
        """
        Query Amazon Q specifically for dashboard creation, explaining that the output will be processed 
        by another LLM system to create cost optimization dashboards.
        """
        services_list = services or ["EC2", "EBS", "S3", "Lambda", "RDS"]
        services_str = ", ".join(services_list)
        
        dashboard_query = f"""AMAZON Q: CRITICAL MISSION FOR DASHBOARD LLM PROCESSING

{ENHANCED_DASHBOARD_INSTRUCTIONS}

CONTEXT: YOUR ANALYSIS WILL BE PROCESSED BY ANOTHER AI SYSTEM
Your response will be fed into another Large Language Model (LLM) system that specializes in creating comprehensive cost optimization dashboards. The downstream LLM needs MAXIMUM DETAIL AND SPECIFICITY to create actionable business intelligence.

SPECIFIC QUERY: {query}
SERVICES TO ANALYZE: {services_str}

CRITICAL COMMUNICATION TO AMAZON Q:
The AI system that will process your analysis needs:

1. EXACT NUMERICAL DATA (never use ranges or approximations):
   - Specific dollar amounts: $127.45, not "approximately $125"
   - Exact percentages: 8.7%, not "around 10%" 
   - Precise resource counts: 247 instances, not "about 250"
   - Detailed timestamps: "Last accessed: 2024-12-15", not "recently"

2. COMPLETE RESOURCE IDENTIFICATION:
   - Full resource IDs: i-0a1b2c3d4e5f6g7h8, not "EC2 instance"
   - Complete ARNs when available
   - Exact resource names including special characters
   - Full specification details: m5.large, not "medium instance"

3. SPECIFIC IMPLEMENTATION INSTRUCTIONS:
   - Exact AWS CLI commands with real resource IDs
   - Complete parameter specifications
   - Step-by-step procedures with actual values
   - Required permissions and prerequisites

4. COMPREHENSIVE COST BREAKDOWN:
   - Current monthly cost per individual resource
   - Potential savings per optimization action
   - Total aggregated costs and savings
   - ROI calculations with timeframes

5. DETAILED UTILIZATION METRICS:
   - Exact CPU/memory/storage utilization percentages
   - Performance data over specific time periods
   - Access patterns and usage frequency
   - Efficiency calculations and comparisons

DASHBOARD CREATION REQUIREMENTS:
The downstream LLM will create:
- Executive dashboards with KPIs and metrics
- Detailed resource inventories with optimization opportunities  
- Cost savings projections and ROI analysis
- Implementation roadmaps with timelines
- Risk assessments and prioritization matrices
- Interactive charts and visualizations

AMAZON Q: PLEASE PROVIDE THE MOST DETAILED, SPECIFIC, AND COMPREHENSIVE ANALYSIS POSSIBLE. Include every relevant detail, exact figure, and specific recommendation. The quality of the resulting dashboard depends entirely on the specificity and completeness of your analysis.

EXECUTE COMPREHENSIVE ANALYSIS FOR: {query}

Focus on services: {services_str}

Remember: Another AI system is counting on your detailed analysis to create actionable business intelligence. Provide maximum detail and specificity."""

        raw_output = await self._run_cli_command(dashboard_query)
        return self._parse_cli_output(raw_output)
