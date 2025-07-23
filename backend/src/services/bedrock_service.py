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
                "output_format": "comprehensive_report",
            }

            input_text = f"""
            CREATE COST OPTIMIZATION DASHBOARD INSIGHTS
            
            AMAZON Q DATA FROM AWS ACCOUNT ANALYSIS:
            {json.dumps(input_data, indent=2)}
            
            MISSION: Analyze the Amazon Q data and create comprehensive dashboard insights with recommendations.
            
            CREATE DASHBOARD CONTENT WITH:
            
            1. EXECUTIVE SUMMARY:
            - Key findings from the AWS analysis
            - Total resources found and their status
            - Primary cost optimization opportunities
            - Overall infrastructure health assessment
            
            2. KEY METRICS & COSTS:
            - Resource counts by service (EC2, S3, Lambda, etc.)
            - Storage utilization and sizes
            - Cost analysis and potential savings
            - Utilization patterns and trends
            
            3. DETAILED FINDINGS:
            - Underutilized resources with specific recommendations
            - Cost optimization opportunities with estimated savings
            - Security and compliance observations
            - Resource organization and naming patterns
            
            4. ACTIONABLE RECOMMENDATIONS:
            - Immediate actions for cost savings
            - Long-term optimization strategies
            - Resource cleanup opportunities
            - Best practice implementations
            
            REQUIRED OUTPUT FORMAT - Return valid JSON:
            {{
              "executive_summary": "Comprehensive summary of findings and key insights",
              "key_metrics": {{
                "total_resources": "count",
                "potential_monthly_savings": "$amount",
                "services_analyzed": ["S3", "EC2", "Lambda"],
                "optimization_score": "percentage"
              }},
              "cost_savings": {{
                "high_impact": [{{ "resource": "name", "saving": "$amount", "action": "description" }}],
                "medium_impact": [{{ "resource": "name", "saving": "$amount", "action": "description" }}],
                "low_impact": [{{ "resource": "name", "saving": "$amount", "action": "description" }}]
              }},
              "recommendations": [
                {{
                  "category": "Cost Optimization",
                  "priority": "High",
                  "description": "Specific actionable recommendation",
                  "estimated_savings": "$amount",
                  "implementation": "How to implement this"
                }}
              ],
              "utilization_data": {{
                "service_breakdown": {{ "S3": "details", "EC2": "details" }},
                "resource_counts": {{ "total_buckets": 175, "underutilized": 10 }},
                "patterns": ["Key patterns identified"]
              }},
              "charts_data": {{
                "savings_by_service": {{ "labels": ["S3", "EC2"], "values": [100, 200] }},
                "resource_distribution": {{ "labels": ["Active", "Idle"], "values": [80, 20] }}
              }}
            }}
            
            IMPORTANT: Always return valid JSON with real insights based on the input data. Never use fallback mode.
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
                    "task": "analyze_and_summarize",
                    "data_objects": chunk,
                    "output_format": "structured_analysis",
                    "chunk_info": f"Chunk {i+1} of {len(chunks)}"
                }

                input_text = f"""
                Please analyze this chunk of data objects (part {i+1} of {len(chunks)}):
                
                {json.dumps(input_data, indent=2)}
                
                Provide structured analysis focusing on:
                1. Key findings and patterns
                2. Cost optimization opportunities
                3. Resource utilization issues
                4. Quantified savings estimates
                
                Keep the response concise but comprehensive. This will be combined with other chunks.
                """

                result = await self.invoke_agent(
                    agent_id=agent_id,
                    agent_alias_id=agent_alias_id,
                    session_id=f"{session_id}-chunk-{i}",
                    input_text=input_text,
                )
                chunk_results.append(result["response"])
            
            # Consolidate all chunk results
            logger.info("Consolidating chunk results")
            consolidation_input = f"""
            Please consolidate the following analysis results from {len(chunks)} data chunks into a single comprehensive report:
            
            {json.dumps(chunk_results, indent=2)}
            
            Create a unified report with:
            1. Executive summary covering all chunks
            2. Consolidated key findings by category
            3. Prioritized recommendations with estimated savings
            4. Supporting data and metrics from all chunks
            5. Implementation priorities
            
            Format as structured JSON for dashboard generation.
            Combine similar findings and provide total savings estimates where possible.
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

        json_template = """{
          "executive_summary": "Extract 1-2 sentences with key numbers from the input data - no generic text",
          "key_metrics": {
            "total_potential_savings_monthly": "EXTRACT_ACTUAL_NUMBER_FROM_INPUT",
            "total_potential_savings_yearly": "MULTIPLY_MONTHLY_BY_12", 
            "underutilized_resources_count": "COUNT_RESOURCE_IDS_FROM_INPUT",
            "optimization_opportunities": "COUNT_RECOMMENDATIONS_FROM_INPUT",
            "highest_impact_service": "FIND_SERVICE_WITH_HIGHEST_COST",
            "implementation_complexity": "low"
          },
          "cost_savings": {
            "by_service": {
              "EC2": "EXTRACT_EC2_COSTS_FROM_INPUT",
              "EBS": "EXTRACT_EBS_COSTS_FROM_INPUT", 
              "S3": "EXTRACT_S3_COSTS_FROM_INPUT", 
              "Lambda": "EXTRACT_LAMBDA_COSTS_FROM_INPUT"
            },
            "by_category": {
              "right_sizing": "EXTRACT_RIGHTSIZING_SAVINGS",
              "termination": "EXTRACT_TERMINATION_SAVINGS",
              "storage_optimization": "EXTRACT_STORAGE_SAVINGS",
              "reserved_instances": "EXTRACT_RI_SAVINGS"
            },
            "top_opportunities": [
              {
                "resource_id": "EXTRACT_ACTUAL_RESOURCE_ID",
                "current_cost": "EXTRACT_ACTUAL_COST", 
                "potential_saving": "EXTRACT_SAVINGS_AMOUNT",
                "action": "EXTRACT_RECOMMENDED_ACTION"
              }
            ]
          },
          "utilization_data": {
            "ec2_underutilized": {
              "count": "COUNT_EC2_INSTANCES_FROM_INPUT",
              "avg_cpu": "EXTRACT_CPU_PERCENTAGE",
              "avg_memory": "EXTRACT_MEMORY_PERCENTAGE"
            },
            "ebs_unattached": {
              "count": "COUNT_UNATTACHED_VOLUMES",
              "wasted_cost": "CALCULATE_WASTED_EBS_COST"
            },
            "s3_idle_buckets": {
              "count": "COUNT_IDLE_BUCKETS",
              "storage_gb": "EXTRACT_STORAGE_SIZE"
            }
          },
          "recommendations": [
            {
              "category": "EXTRACT_CATEGORY_FROM_INPUT",
              "description": "EXTRACT_ACTUAL_RECOMMENDATION_TEXT",
              "estimated_savings": "EXTRACT_SAVINGS_NUMBER",
              "priority_score": "CALCULATE_BASED_ON_SAVINGS",
              "implementation": "EXTRACT_IMPLEMENTATION_STEPS",
              "resource_ids": ["EXTRACT_ALL_RESOURCE_IDS_MENTIONED"]
            }
          ],
          "charts_data": {
            "savings_by_service": {
              "labels": ["EC2", "S3", "EBS", "Lambda"],
              "values": ["USE_ACTUAL_NUMBERS_FROM_BY_SERVICE_ABOVE"]
            },
            "utilization_trends": {
              "ec2": ["EXTRACT_EC2_UTILIZATION_VALUES"],
              "ebs": ["EXTRACT_EBS_UTILIZATION_VALUES"],
              "s3": ["EXTRACT_S3_UTILIZATION_VALUES"]
            },
            "opportunity_priority": {
              "high": ["OPPORTUNITIES_OVER_1000_SAVINGS"],
              "medium": ["OPPORTUNITIES_100_TO_1000_SAVINGS"],
              "low": ["OPPORTUNITIES_UNDER_100_SAVINGS"]
            }
          },
          "dashboard_config": {
            "primary_color": "#FF6B35",
            "theme": "cost_optimization",
            "layout": "grid", 
            "chart_types": ["bar", "donut", "line", "scatter"]
          }
        }"""

        input_text = f"""
        CREATE COMPREHENSIVE COST OPTIMIZATION DASHBOARD SUMMARY
        
        PROCESSED AWS ANALYSIS DATA:
        {processed_data}
        
        MISSION: Transform the AWS analysis into a comprehensive dashboard summary with actionable insights.
        
        REQUIRED OUTPUT: Always return a valid dashboard JSON with these components:
        
        1. EXECUTIVE SUMMARY: Clear overview of findings and opportunities
        2. KEY METRICS: Resource counts, potential savings, optimization scores  
        3. COST SAVINGS: Categorized by impact level and service
        4. RECOMMENDATIONS: Specific actionable items with priorities
        5. UTILIZATION DATA: Service breakdowns and usage patterns
        6. CHARTS DATA: Data formatted for visualizations
        
        ALWAYS USE THIS DASHBOARD JSON FORMAT:
        {{
          "executive_summary": "Based on the AWS analysis, provide a clear summary of key findings, total resources analyzed, and primary optimization opportunities identified.",
          "key_metrics": {{
            "total_resources": "Count of resources analyzed (e.g., buckets, instances)",
            "potential_monthly_savings": "Estimated monthly savings (use $0 if no specific costs found)",
            "services_analyzed": ["List services found in analysis"],
            "optimization_score": "Overall efficiency percentage (estimate based on findings)"
          }},
          "cost_savings": {{
            "high_impact": [{{ "resource": "resource name", "saving": "estimated amount", "action": "recommended action" }}],
            "medium_impact": [{{ "resource": "resource name", "saving": "estimated amount", "action": "recommended action" }}],
            "low_impact": [{{ "resource": "resource name", "saving": "estimated amount", "action": "recommended action" }}]
          }},
          "recommendations": [
            {{
              "category": "Cost Optimization / Security / Performance",
              "priority": "High / Medium / Low",
              "description": "Specific actionable recommendation based on findings",
              "estimated_savings": "Dollar amount or benefit",
              "implementation": "How to implement this recommendation"
            }}
          ],
          "utilization_data": {{
            "service_breakdown": {{ "S3": "details from analysis", "EC2": "details if found" }},
            "resource_counts": {{ "total_buckets": "number found", "categories": "count by type" }},
            "patterns": ["Key organizational or usage patterns identified"]
          }},
          "charts_data": {{
            "savings_by_service": {{ "labels": ["S3", "EC2", "Lambda"], "values": [100, 50, 25] }},
            "resource_distribution": {{ "labels": ["Active", "Development", "Testing"], "values": [60, 25, 15] }},
            "utilization_trends": {{ "categories": ["Application", "Development", "Infrastructure"], "counts": [80, 30, 20] }}
          }}
        }}
        
        CRITICAL REQUIREMENTS:
        - ALWAYS return valid JSON starting with {{ and ending with }}
        - NEVER use raw_data_fallback status - always create a proper dashboard
        - Base insights on actual data from the input
        - If specific costs aren't available, focus on resource optimization and best practices
        - Make recommendations actionable and specific to the findings
        - Ensure all JSON fields are properly formatted
        """

        return await self.invoke_agent(
            agent_id=agent_id,
            agent_alias_id=agent_alias_id,
            session_id=session_id,
            input_text=input_text,
        )
