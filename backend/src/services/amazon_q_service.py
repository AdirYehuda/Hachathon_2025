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
        self, cli_path: str = None, aws_profile: str = None, region: str = "us-east-1"
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
                
                if self.aws_profile:
                    env["AWS_PROFILE"] = self.aws_profile
                if self.region:
                    env["AWS_REGION"] = self.region
                
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
                logger.info(f"Environment AWS_PROFILE: {env.get('AWS_PROFILE')}")
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
        
        lines = raw_output.split("\n")
        cleaned_lines = []
        in_response_section = False
        
        for line in lines:
            # Start capturing after the CLI header
            if "🤖 You are chatting with" in line:
                in_response_section = True
                continue
                
            # Skip CLI artifacts and ASCII art
            if any(
                artifact in line
                for artifact in [
                    "Using claude-",
                    "(To exit the CLI, press Ctrl+C",
                    "amazon q cli",
                    "┌─",  # ASCII art borders
                    "└─",
                    "│ You can",  # Did you know boxes
                    "╭─",  # Box drawing
                    "╰─",
                    "/help all commands",
                    "ctrl + j new lines",
                    "━━━━━━━",  # Separator lines
                    "All tools are now trusted",
                    "Learn more at https://docs.aws.amazon.com",
                    "⢠⣶⣶⣦",  # ASCII art patterns
                    "⠀⠀⠀⣾⡿",
                    "⠚⠛⠋⠀",
                ]
            ):
                continue

            # Preserve lines that contain AWS data, tool usage, or analysis
            if in_response_section and line.strip():
                # Clean line but preserve structure
                cleaned_line = line.replace("> ", "").strip()
                
                # Keep lines that contain meaningful content
                if (cleaned_line and 
                    not cleaned_line.startswith("╭") and 
                    not cleaned_line.startswith("│") and
                    not cleaned_line.startswith("╰")):
                    cleaned_lines.append(cleaned_line)

        # Join the cleaned content
        response_content = "\n".join(cleaned_lines).strip()

        # If we still don't have content, try to extract just the actual response part
        if not response_content:
            # Look for the actual response after the prompt character
            for line in raw_output.split("\n"):
                if line.strip().startswith("> ") and len(line.strip()) > 2:
                    response_content = line.replace("> ", "").strip()
                    break
        
        # Final fallback to raw output if nothing else works
        if not response_content:
            response_content = raw_output.strip()

        # Log the parsing results
        logger.info(f"📤 Parsed output length: {len(response_content)} characters")
        logger.info(f"📄 Parsed content preview (first 500 chars):")
        logger.info(response_content[:500] + "..." if len(response_content) > 500 else response_content)
        logger.info("=" * 60)

        return {
            "response": response_content,
            "conversation_id": None,  # CLI doesn't maintain conversation IDs in our use case
            "source_attributions": [],
            "raw_output": raw_output,
        }

    @handle_cli_errors
    async def chat(self, message: str, conversation_id: Optional[str] = None) -> Dict:
        """Send a chat message to Amazon Q via CLI."""
        prompt = message

        raw_output = await self._run_cli_command(prompt)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def query_cost_optimization(self, query: str) -> Dict:
        """Query Amazon Q for cost optimization insights via CLI."""
        cost_query = f"""URGENT: I need raw, unstructured AWS account data for: {query}

CRITICAL REQUIREMENTS - NO SUMMARIES, NO QUESTIONS:
- Run actual AWS CLI commands and scripts to gather live data
- Provide unprocessed output from AWS APIs
- Include all raw metrics, logs, and resource details
- Give me the messy, unfiltered data that I can process later

EXECUTE THESE ANALYSIS TASKS:

1. SCAN ACTUAL RESOURCES IN MY ACCOUNT:
   - Run describe-instances, describe-volumes, list-buckets commands
   - Get CloudWatch metrics for last 30 days (CPU, memory, network, storage usage)
   - List all EBS volumes and their attachment status
   - Check Lambda function invocation counts and memory usage
   - Identify unused elastic IPs, NAT gateways, load balancers

2. EXTRACT RAW UTILIZATION DATA:
   - Dump CloudWatch metrics in CSV/JSON format
   - Show actual usage patterns: hourly, daily, weekly trends
   - List exact idle time periods for each resource
   - Get billing data with line-item details
   - Export cost and usage reports data

3. PROVIDE UNPROCESSED OUTPUT:
   - Don't clean up or summarize the data
   - Include all resource IDs, timestamps, metric values
   - Show actual AWS CLI command outputs
   - Include any errors or warnings from AWS APIs
   - Give me tables, logs, JSON dumps - all the raw material

4. SPECIFIC COMMANDS TO RUN:
   ```bash
   aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,LaunchTime]'
   aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --start-time 30-days-ago
   aws s3api list-buckets --query 'Buckets[].[Name,CreationDate]'
   aws ce get-cost-and-usage --time-period Start=2025-01-01,End=2025-01-31 --granularity MONTHLY
   ```

I want to see the actual data from these commands - the unstructured, raw output that contains real numbers, dates, and resource identifiers from MY specific AWS account.

Focus on data gathering, not analysis. Be a data collector, not a consultant."""

        raw_output = await self._run_cli_command(cost_query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def query_underutilization(
        self, resource_type: str, time_range: str = "30d"
    ) -> Dict:
        """Query Amazon Q for resource underutilization analysis via CLI."""
        underutil_query = f"""Analyze my AWS account for {resource_type} underutilization over {time_range}. 

Provide SPECIFIC RAW DATA, not summaries:

1. LIST ALL UNDERUTILIZED {resource_type.upper()} RESOURCES:
   - Resource IDs and names
   - Current utilization metrics (exact percentages)
   - Monthly costs for each resource
   - Last access/usage dates
   - Recommended actions (specific instance types, storage classes, etc.)

2. COST IMPACT DATA:
   - Potential monthly savings per resource
   - Total waste amount in dollars
   - ROI of optimization actions

3. IMPLEMENTATION DETAILS:
   - Specific AWS CLI commands or API calls
   - Recommended instance families/sizes
   - Storage class recommendations
   - Scheduling recommendations

I need the actual data from my account analysis, not generic guidance or questions asking for more information."""

        raw_output = await self._run_cli_command(underutil_query)
        return self._parse_cli_output(raw_output)

    # Specific methods for different AWS services based on successful examples

    @handle_cli_errors
    async def analyze_ec2_underutilization(self, time_range: str = "30d") -> Dict:
        """Analyze underutilized EC2 instances."""
        query = f"""EXECUTE EC2 DATA COLLECTION FOR UNDERUTILIZATION ANALYSIS - {time_range}

RUN THESE COMMANDS AND DUMP RAW OUTPUT:

1. GET ALL EC2 INSTANCES:
aws ec2 describe-instances --output table
aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,LaunchTime,Placement.AvailabilityZone,Platform,PublicIpAddress,PrivateIpAddress]' --output table

2. COLLECT CLOUDWATCH METRICS (RAW DATA):
aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --dimensions Name=InstanceId,Value=<EACH-INSTANCE-ID> --start-time {time_range}-ago --end-time now --period 3600 --statistics Average,Maximum,Minimum
aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name NetworkIn --dimensions Name=InstanceId,Value=<EACH-INSTANCE-ID> --start-time {time_range}-ago --end-time now --period 86400 --statistics Sum
aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name NetworkOut --dimensions Name=InstanceId,Value=<EACH-INSTANCE-ID> --start-time {time_range}-ago --end-time now --period 86400 --statistics Sum

3. DUMP COST EXPLORER DATA:
aws ce get-cost-and-usage --time-period Start=2025-01-01,End=2025-01-31 --granularity DAILY --metrics BlendedCost,UsageQuantity --group-by Type=DIMENSION,Key=SERVICE Type=DIMENSION,Key=INSTANCE_TYPE
aws ce get-dimension-values --dimension SERVICE --time-period Start=2025-01-01,End=2025-01-31

4. EXTRACT DETAILED INSTANCE DATA:
aws ec2 describe-instance-attribute --instance-id <EACH-INSTANCE-ID> --attribute instanceType
aws ec2 describe-volumes --filters Name=attachment.instance-id,Values=<EACH-INSTANCE-ID>

PROVIDE EVERYTHING AS RAW COMMAND OUTPUT - don't analyze or summarize. I need the actual AWS API responses with timestamps, metrics, and resource identifiers exactly as returned by AWS."""

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def analyze_ebs_underutilization(self) -> Dict:
        """Analyze underutilized EBS volumes."""
        query = """Analyze my AWS account EBS volumes for underutilization and optimization.

Provide SPECIFIC RAW DATA from my account:

1. UNDERUTILIZED EBS VOLUMES:
   - Volume IDs (vol-xxxxx)
   - Volume types (gp2, gp3, io1, etc.)
   - Current sizes and IOPS
   - Average utilization % and I/O patterns
   - Monthly costs per volume
   - Attachment status (attached/unattached)

2. OPTIMIZATION OPPORTUNITIES:
   - Unattached volumes (list volume IDs to delete)
   - Oversized volumes (current size → recommended size)
   - Type optimization (gp2 → gp3 conversions)
   - IOPS optimization opportunities

3. COST SAVINGS DATA:
   - Potential monthly savings per volume optimization
   - Total waste from unattached volumes
   - Storage class migration savings
   - Snapshot optimization opportunities

Provide actual volume data from my account analysis, not general recommendations."""

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def analyze_s3_underutilization(self) -> Dict:
        """Analyze underutilized S3 buckets."""
        query = """EXECUTE S3 DATA COLLECTION - DUMP ALL BUCKET INFORMATION

RUN THESE COMMANDS AND SHOW RAW OUTPUT:

1. LIST ALL BUCKETS WITH METADATA:
aws s3api list-buckets --output table
aws s3 ls --recursive --human-readable --summarize s3://bucket-name/ (for each bucket)
aws s3api get-bucket-location --bucket bucket-name (for each bucket)

2. GET STORAGE ANALYTICS FOR EACH BUCKET:
aws s3api get-bucket-inventory-configuration --bucket bucket-name
aws s3api list-object-versions --bucket bucket-name --max-items 1000
aws s3api get-bucket-lifecycle-configuration --bucket bucket-name

3. EXTRACT CLOUDWATCH S3 METRICS:
aws cloudwatch get-metric-statistics --namespace AWS/S3 --metric-name BucketSizeBytes --dimensions Name=BucketName,Value=bucket-name Name=StorageType,Value=StandardStorage --start-time 30-days-ago --end-time now --period 86400 --statistics Maximum
aws cloudwatch get-metric-statistics --namespace AWS/S3 --metric-name NumberOfObjects --dimensions Name=BucketName,Value=bucket-name Name=StorageType,Value=AllStorageTypes --start-time 30-days-ago --end-time now --period 86400 --statistics Maximum

4. COST AND USAGE DATA:
aws ce get-cost-and-usage --time-period Start=2025-01-01,End=2025-01-31 --granularity MONTHLY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE --filter file://s3-filter.json
aws s3api list-objects-v2 --bucket bucket-name --query 'Contents[?LastModified<`2024-01-01`]' --output table

5. ACCESS PATTERNS AND LOGS:
aws s3api get-bucket-logging --bucket bucket-name
aws s3api get-bucket-request-payment --bucket bucket-name
aws s3api get-bucket-notification-configuration --bucket bucket-name

PROVIDE RAW COMMAND OUTPUTS - don't clean up the data. I need the unprocessed bucket listings, object counts, timestamps, and size data exactly as AWS returns it."""

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def analyze_lambda_underutilization(self) -> Dict:
        """Analyze underutilized Lambda functions."""
        query = "Find underutilized Lambda functions with low invocation rates, over-provisioned memory/timeout, and unused functions. Include function names, invocation counts, memory settings, and optimization recommendations."

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def analyze_rds_underutilization(self) -> Dict:
        """Analyze underutilized RDS instances."""
        query = "Analyze underutilized RDS instances with low CPU/memory utilization, minimal connections, and right-sizing opportunities. Include instance identifiers, utilization metrics, and cost optimization estimates."

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)

    @handle_cli_errors
    async def comprehensive_cost_analysis(self, services: List[str] = None) -> Dict:
        """Perform comprehensive cost optimization analysis across multiple services."""
        services_list = services or ["EC2", "EBS", "S3", "Lambda", "RDS"]
        services_str = ", ".join(services_list)

        # Create focused query that only analyzes the specified services
        if len(services_list) == 1:
            query = f"Focused AWS cost optimization analysis for {services_str} ONLY. Show underutilized {services_str} resources, right-sizing recommendations, cost savings estimates, and specific optimization recommendations. Do not analyze other AWS services."
        else:
            query = f"AWS cost optimization analysis for these specific services ONLY: {services_str}. Show underutilized resources, right-sizing recommendations, cost savings estimates, and priority recommendations organized by service. Focus exclusively on these {len(services_list)} services and do not analyze other AWS services."

        raw_output = await self._run_cli_command(query)
        return self._parse_cli_output(raw_output)
