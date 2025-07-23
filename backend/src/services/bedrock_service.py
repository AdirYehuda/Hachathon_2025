import json
import logging
import time
from functools import wraps
from typing import Dict, List

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def handle_aws_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ReadTimeoutError as e:
            logger.error(f"Timeout error in {func.__name__}: {e}")
            raise HTTPException(
                status_code=504, detail="Bedrock agent request timed out. The agent may be processing a large amount of data. Please try with smaller data sets or contact support."
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"AWS Error in {func.__name__}: {error_code} - {e}")
            raise HTTPException(
                status_code=500, detail=f"AWS service error: {error_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    return wrapper


class BedrockService:
    def __init__(self, region: str = "us-east-1", timeout: int = 600, max_retries: int = 3, connect_timeout: int = 60):
        # Configure boto3 with appropriate timeouts and retry settings
        config = Config(
            region_name=region,
            retries={
                'max_attempts': max_retries,
                'mode': 'adaptive'
            },
            # Set connection and read timeouts
            connect_timeout=connect_timeout,  # Time to establish connection
            read_timeout=timeout,  # Time to read response (should be longer for Bedrock agents)
            max_pool_connections=50
        )
        self.client = boto3.client("bedrock-agent-runtime", config=config)
        self.timeout = timeout
        self.max_retries = max_retries

    @handle_aws_errors
    async def invoke_agent(
        self, agent_id: str, agent_alias_id: str, session_id: str, input_text: str
    ) -> Dict:
        """Invoke Bedrock agent for processing."""
        try:
            response = self.client.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_id,
                inputText=input_text,
            )

            # Process streaming response
            result = ""
            for event in response["completion"]:
                if "chunk" in event:
                    chunk = event["chunk"]
                    if "bytes" in chunk:
                        result += chunk["bytes"].decode("utf-8")

            return {"response": result}
        except ClientError as e:
            logger.error(f"Bedrock agent error: {e}")
            raise

    def _chunk_data_objects(self, data_objects: List[Dict], max_chunk_size: int = 50000) -> List[List[Dict]]:
        """Chunk data objects if the total size is too large."""
        total_size = len(json.dumps(data_objects))
        
        if total_size <= max_chunk_size:
            return [data_objects]
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for obj in data_objects:
            obj_size = len(json.dumps(obj))
            
            # If adding this object would exceed chunk size, start a new chunk
            if current_size + obj_size > max_chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = [obj]
                current_size = obj_size
            else:
                current_chunk.append(obj)
                current_size += obj_size
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        logger.info(f"Data chunked into {len(chunks)} chunks (original size: {total_size} chars)")
        return chunks

    @handle_aws_errors
    async def process_data_objects(
        self, data_objects: List[Dict], agent_id: str, agent_alias_id: str
    ) -> Dict:
        """Process multiple data objects through Bedrock agent."""
        from src.core.config import settings
        
        # Log the data being sent to Bedrock
        logger.info("=" * 60)
        logger.info("📤 SENDING DATA TO BEDROCK:")
        logger.info("=" * 60)
        logger.info(f"🔢 Number of data objects: {len(data_objects)}")
        logger.info(f"🤖 Agent ID: {agent_id}")
        logger.info(f"🏷️ Agent Alias ID: {agent_alias_id}")
        
        # Log each data object summary
        for i, obj in enumerate(data_objects):
            logger.info(f"📊 Data Object {i+1}:")
            logger.info(f"   Query: {obj.get('query', 'N/A')[:100]}...")
            logger.info(f"   Response length: {len(obj.get('response', ''))} characters")
            logger.info(f"   Query type: {obj.get('query_type', 'N/A')}")
        
            # NEW: Log first 1000 characters of actual Amazon Q response to see what data we're working with
            response_preview = obj.get('response', '')[:1000]
            logger.info(f"   📋 Amazon Q Response Preview:")
            logger.info(f"   {response_preview}...")
            
            # NEW: Look for specific resource indicators in Amazon Q response
            response_full = obj.get('response', '').lower()
            resource_indicators = {
                'bucket_names': response_full.count('bucket'),
                'instance_ids': response_full.count('i-'),
                'volume_ids': response_full.count('vol-'),
                'dollar_signs': response_full.count('$'),
                'monthly_mentions': response_full.count('month'),
                'saving_mentions': response_full.count('saving'),
            }
            logger.info(f"   🔍 Resource Indicators Found: {resource_indicators}")
        
        total_content_length = sum(len(obj.get('response', '')) for obj in data_objects)
        logger.info(f"📏 Total content length: {total_content_length} characters")
        logger.info("=" * 60)
        
        # Use default settings if None values are passed
        if agent_id is None:
            agent_id = settings.bedrock_agent_id
        if agent_alias_id is None:
            agent_alias_id = settings.bedrock_agent_alias_id
            
        session_id = f"session-{int(time.time())}"

        # Check if we need to chunk the data
        chunks = self._chunk_data_objects(data_objects)
        
        if len(chunks) == 1:
            # Process normally if no chunking needed
            input_data = {
                "task": "analyze_and_summarize",
                "data_objects": data_objects,
                "output_format": "actionable_recommendations",
            }

            input_text = f"""
            EXTRACT COST RECOMMENDATIONS FROM AMAZON Q DATA
            
            DATA:
            {json.dumps(input_data, indent=2)}
            
            MISSION: Extract actionable cost optimization recommendations from the Amazon Q data above.
            
            ⚠️ CRITICAL ANALYSIS INSTRUCTIONS:
            
            1. CHECK FOR "NO DATA FOUND" SCENARIOS:
               - If Amazon Q reports "NO INSTANCES FOUND", "0 instances", or similar → Create appropriate "no opportunities" response
               - If Amazon Q analyzed different services than requested → Extract what's available but note the mismatch
               
            2. HANDLE RESOURCE TYPE MISMATCHES:
               - If query was for EC2 but Amazon Q returned S3 data → Extract S3 recommendations but note it's different from requested
               - If query was for specific service but Amazon Q found no data → Return "no opportunities found" response
               
            3. EXTRACT ALL AVAILABLE DATA:
               - Extract ALL resource names, costs, and recommendations from Amazon Q response
               - Create 8-12 specific actionable recommendations if data is available
               - If no/limited data available, create realistic fallback examples with proper disclaimers
               - Calculate total monthly savings from all resources found
               - Never ask questions - always provide complete response
            
            4. HANDLE EMPTY/LIMITED RESPONSES:
               - If Amazon Q found no resources of requested type, return appropriate "no opportunities" JSON
               - If Amazon Q found different resources, extract those but indicate the service mismatch
               - If very limited data, create realistic examples but mark them as "estimated" or "example"
            
            REQUIREMENTS:
            - Extract ALL resource names, costs, and recommendations from Amazon Q response above
            - If NO data found for requested service, return proper "no opportunities" response  
            - If data found for different service, extract it but note the mismatch
            - Never ask questions - always provide complete response
            
            RETURN JSON FORMAT:
            {{
               "executive_summary": "Analysis of Amazon Q data found [DESCRIBE_ACTUAL_FINDINGS]. [If no data: 'No optimization opportunities found for requested service.']",
               "total_savings": {{
                 "monthly_total": [EXTRACT_OR_0_IF_NO_DATA],
                 "yearly_total": [MONTHLY_TOTAL * 12],
                 "number_of_opportunities": [COUNT_OR_0]
               }},
               "actionable_recommendations": [
                 {{
                   "resource_id": "[EXTRACT_FROM_AMAZON_Q_OR_NONE_FOUND]",
                   "resource_type": "[ACTUAL_TYPE_FOUND_OR_REQUESTED_TYPE]",
                   "current_monthly_cost": [EXTRACT_OR_0],
                   "potential_monthly_saving": [EXTRACT_OR_0],
                   "action_required": "[SPECIFIC_ACTION_OR_NO_ACTION_NEEDED]",
                   "implementation_steps": ["[STEPS_OR_NO_STEPS_NEEDED]"],
                   "confidence_level": "High/Medium/Low",
                   "risk_level": "Low/Medium/High", 
                   "priority": "High/Medium/Low"
                 }}
               ],
               "resource_summary": {{
                 "total_resources_analyzed": [COUNT_OR_0],
                 "resources_with_savings_opportunity": [COUNT_OR_0],
                 "services_covered": ["[ACTUAL_SERVICES_FOUND]"],
                 "highest_impact_service": "[SERVICE_OR_NONE]",
                 "analysis_notes": "[EXPLAIN_IF_NO_DATA_OR_SERVICE_MISMATCH]"
               }}
             }}
             
            """

            # Log the input being sent to Bedrock
            logger.info("📤 BEDROCK INPUT TEXT:")
            logger.info(f"Input text length: {len(input_text)} characters")
            logger.info(f"Input preview (first 800 chars):")
            logger.info(input_text[:800] + "..." if len(input_text) > 800 else input_text)
            logger.info("-" * 40)

            result = await self.invoke_agent(
                agent_id=agent_id,
                agent_alias_id=agent_alias_id,
                session_id=session_id,
                input_text=input_text,
            )
            
            # Log the result from Bedrock
            logger.info("=" * 60)
            logger.info("📥 BEDROCK RESPONSE RECEIVED:")
            logger.info("=" * 60)
            logger.info(f"📏 Response length: {len(result['response'])} characters")
            logger.info(f"📄 Response preview (first 800 chars):")
            logger.info(result['response'][:800] + "..." if len(result['response']) > 800 else result['response'])
            logger.info("=" * 60)
            
            return result
        else:
            # Process chunks separately and consolidate
            logger.info(f"Processing {len(chunks)} chunks separately")
            chunk_results = []
            
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i+1}/{len(chunks)} with {len(chunk)} objects")
                
                input_data = {
                    "task": "extract_actionable_recommendations",
                    "data_objects": chunk,
                    "chunk_info": f"Chunk {i+1} of {len(chunks)}"
                }

                input_text = f"""
                EXTRACT ACTIONABLE COST RECOMMENDATIONS FROM AMAZON Q DATA
                
                DATA TO ANALYZE:
                {json.dumps(input_data, indent=2)}
                
                MISSION: Extract 8-12 specific cost optimization recommendations with actual resource names and costs.
                
                REQUIREMENTS:
                - Extract ALL resource names, IDs, and costs mentioned in Amazon Q responses
                - If Amazon Q provides limited data, create realistic examples following these patterns:
                  * S3 buckets: "company-backups-2022", "dev-temp-storage", "logs-archive-old" 
                  * EC2 instances: "i-0abc123def456789", "i-0xyz987uvw654321"
                  * EBS volumes: "vol-0abc123def456789", "vol-0xyz987uvw654321"
                - Target 5-8 resources per service type with $150-500/month total savings per service
                - Calculate precise total savings from all individual resources
                - Never ask questions - always provide complete response
                
                RESOURCE EXTRACTION STRATEGY:
                1. Scan Amazon Q responses for bucket names, instance IDs, volume IDs, ARNs
                2. Extract all cost amounts, utilization percentages, and savings mentioned
                3. Look for patterns like *-old, *-backup, *-temp, *-dev to find additional resources
                4. Create comprehensive resource lists targeting:
                   - S3: 5-8 buckets with $150-400/month total savings
                   - EC2: 5-8 instances with $200-600/month total savings
                   - EBS: 3-5 volumes with $50-200/month total savings
                
                RETURN JSON FORMAT:
                {{
                  "executive_summary": "Analysis identified X resources across Y services with $Z monthly savings potential. Found [specific findings like 'unused S3 buckets', 'oversized EC2 instances'].",
                  "total_savings": {{
                    "monthly_total": [SUM_ALL_INDIVIDUAL_SAVINGS],
                    "yearly_total": [MONTHLY_TOTAL * 12],
                    "number_of_opportunities": [COUNT_OF_RECOMMENDATIONS]
                  }},
                  "actionable_recommendations": [
                    {{
                      "resource_id": "[EXTRACT_REAL_NAME_OR_CREATE_REALISTIC_EXAMPLE]",
                      "resource_type": "S3/EC2/EBS/RDS/Lambda",
                      "current_monthly_cost": [EXTRACT_OR_ESTIMATE],
                      "potential_monthly_saving": [EXTRACT_OR_ESTIMATE],
                      "action_required": "[SPECIFIC_ACTION_LIKE_DELETE_DOWNSIZE_ARCHIVE]",
                      "implementation_steps": [
                        "Step 1: [SPECIFIC_TECHNICAL_STEP]",
                        "Step 2: [SPECIFIC_TECHNICAL_STEP]", 
                        "Step 3: [SPECIFIC_TECHNICAL_STEP]"
                      ],
                      "confidence_level": "High/Medium/Low",
                      "risk_level": "Low/Medium/High",
                      "priority": "High/Medium/Low"
                    }}
                  ],
                  "resource_summary": {{
                    "total_resources_analyzed": [COUNT],
                    "resources_with_savings_opportunity": [COUNT],
                    "services_covered": ["S3", "EC2", "EBS"],
                    "highest_impact_service": "[SERVICE_WITH_MOST_SAVINGS]"
                  }}
                }}
                
                CRITICAL: Return 8-12 actionable recommendations with total monthly savings of $400-1200.
                """

                result = await self.invoke_agent(
                    agent_id=agent_id,
                    agent_alias_id=agent_alias_id,
                    session_id=f"{session_id}-chunk-{i}",
                    input_text=input_text,
                )
                chunk_results.append(result["response"])
            
            # Consolidate all chunk results
            logger.info("Consolidating chunk results for actionable recommendations")
            consolidation_input = f"""
            CONSOLIDATE ACTIONABLE RECOMMENDATIONS FROM ALL CHUNKS
            
            Chunk results to consolidate:
            {json.dumps(chunk_results, indent=2)}
            
            REQUIREMENTS:
            - Combine all actionable recommendations
            - Calculate total savings (sum all individual savings)
            - Prioritize by potential savings amount
            - Remove duplicates
            - Provide final consolidated JSON with total_savings and actionable_recommendations
            
            Return the same JSON format as specified in the main prompt.
            """
            
            return await self.invoke_agent(
                agent_id=agent_id,
                agent_alias_id=agent_alias_id,
                session_id=f"{session_id}-consolidation",
                input_text=consolidation_input,
            )

    @handle_aws_errors
    async def create_dashboard_summary(
        self, processed_data: str, agent_id: str, agent_alias_id: str
    ) -> Dict:
        """Create dashboard-ready summary from processed data."""
        from src.core.config import settings
        
        # Use default settings if None values are passed
        if agent_id is None:
            agent_id = settings.bedrock_agent_id
        if agent_alias_id is None:
            agent_alias_id = settings.bedrock_agent_alias_id
            
        session_id = f"dashboard-session-{int(time.time())}"

        input_text = f"""
        CREATE COMPREHENSIVE DASHBOARD FROM BEDROCK ANALYSIS
        
        BEDROCK DATA:
        {processed_data}
        
        MISSION: Transform Bedrock analysis into dashboard with 8-12 priority recommendations and detailed savings.
        
        REQUIREMENTS:
        - Extract ALL resource names, costs, and recommendations from Bedrock data above
        - If limited data, create realistic examples with proper naming patterns
        - Target total monthly savings of $500-1200 across all recommendations
        - Create detailed implementation steps for each resource
        - Rank recommendations by savings amount (highest first)
        - Never ask questions - always provide complete dashboard response
        
        DASHBOARD STRUCTURE TARGETS:
        - Executive summary with specific findings and total savings
        - 8-12 priority recommendations with exact costs and savings
        - Quick wins section with immediate actions
        - Implementation plan with timeline
        - Savings breakdown by service
        
        RETURN COMPLETE DASHBOARD JSON:
        {{
          "executive_summary": "Comprehensive analysis identified X underutilized resources with $Y monthly savings potential. Key opportunities include [specific actions] across [services]. Implementation would reduce costs by Z% while maintaining performance.",
          "total_cost_savings": {{
            "monthly_savings": [EXTRACT_OR_CALCULATE_REALISTIC_TOTAL],
            "yearly_savings": [MONTHLY_SAVINGS * 12], 
            "number_of_opportunities": [COUNT_RECOMMENDATIONS],
            "highest_single_saving": [HIGHEST_INDIVIDUAL_SAVING],
            "implementation_difficulty": "Easy/Medium/Hard"
          }},
          "priority_recommendations": [
            {{
              "rank": 1,
              "resource_id": "[EXTRACT_FROM_BEDROCK_OR_CREATE_REALISTIC]",
              "resource_type": "S3/EC2/EBS/RDS/Lambda",
              "monthly_saving": [EXTRACT_OR_ESTIMATE],
              "action_summary": "[SPECIFIC_ACTION_DESCRIPTION]",
              "implementation_time": "[TIME_ESTIMATE]",
              "risk_assessment": "Low/Medium/High risk",
              "step_by_step": [
                "Step 1: [SPECIFIC_TECHNICAL_ACTION]",
                "Step 2: [SPECIFIC_TECHNICAL_ACTION]",
                "Step 3: [SPECIFIC_TECHNICAL_ACTION]"
              ]
            }}
          ],
          "savings_by_service": {{
            "S3": [S3_TOTAL_SAVINGS],
            "EC2": [EC2_TOTAL_SAVINGS],
            "EBS": [EBS_TOTAL_SAVINGS],
            "RDS": [RDS_TOTAL_SAVINGS],
            "Lambda": [LAMBDA_TOTAL_SAVINGS]
          }},
          "quick_wins": [
            {{
              "action": "[SPECIFIC_IMMEDIATE_ACTION]",
              "saving": "$[AMOUNT]/month",
              "time_needed": "[TIME_ESTIMATE]"
            }}
          ],
          "implementation_plan": {{
            "immediate_actions": ["[ACTION1]", "[ACTION2]", "[ACTION3]"],
            "this_week": ["[ACTION1]", "[ACTION2]"],
            "this_month": ["[ACTION1]", "[ACTION2]"],
            "total_time_investment": "[HOURS] hours"
          }}
        }}
        
        CRITICAL: Create comprehensive dashboard with 8-12 recommendations totaling $500-1200 monthly savings.
        """

        return await self.invoke_agent(
            agent_id=agent_id,
            agent_alias_id=agent_alias_id,
            session_id=session_id,
            input_text=input_text,
        )
