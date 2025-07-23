import logging
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.api.dependencies import AmazonQServiceDep, ConfigValidationDep
from src.models.requests import CostOptimizationQuery, UnderutilizationQuery
from src.models.responses import AmazonQResponse, create_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/amazon-q", tags=["Amazon Q"])


@router.post("/cost-optimization", response_model=dict)
async def query_cost_optimization(
    request: CostOptimizationQuery,
    amazon_q: AmazonQServiceDep,
    config_valid: ConfigValidationDep,
):
    """
    Query Amazon Q for cost optimization insights.

    This endpoint analyzes your AWS infrastructure and provides recommendations for:
    - Cost reduction opportunities
    - Resource right-sizing
    - Reserved instance recommendations
    - Storage optimization
    """
    try:
        logger.info(f"Processing cost optimization query: {request.query[:100]}...")

        # Query Amazon Q for cost optimization
        result = await amazon_q.query_cost_optimization(request.query)

        # Create response
        response_data = AmazonQResponse(
            query=request.query,
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="cost_optimization",
        )

        return create_response(
            data=response_data.dict(),
            message="Cost optimization analysis completed successfully",
        )

    except Exception as e:
        logger.error(f"Error in cost optimization query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/underutilization", response_model=dict)
async def query_underutilization(
    request: UnderutilizationQuery,
    amazon_q: AmazonQServiceDep,
    config_valid: ConfigValidationDep,
):
    """
    Query Amazon Q for resource underutilization analysis.

    This endpoint analyzes specific resource types for:
    - Underutilized resources
    - Current utilization metrics
    - Optimization recommendations
    - Potential cost savings
    """
    try:
        logger.info(f"Processing underutilization query for {request.resource_type}")

        # Query Amazon Q for underutilization
        result = await amazon_q.query_underutilization(
            resource_type=request.resource_type, time_range=request.time_range
        )

        # Create response
        response_data = AmazonQResponse(
            query=f"Underutilization analysis for {request.resource_type} over {request.time_range}",
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="underutilization",
        )

        return create_response(
            data=response_data.dict(),
            message=f"Underutilization analysis for {request.resource_type} completed successfully",
        )

    except Exception as e:
        logger.error(f"Error in underutilization query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=dict)
async def chat_with_amazon_q(
    message: str,
    amazon_q: AmazonQServiceDep,
    config_valid: ConfigValidationDep,
    conversation_id: str = None,
):
    """
    Direct chat interface with Amazon Q.

    This endpoint provides a direct chat interface for custom queries.
    """
    try:
        logger.info(f"Processing chat message: {message[:100]}...")

        # Chat with Amazon Q
        result = await amazon_q.chat(message, conversation_id)

        # Create response
        response_data = AmazonQResponse(
            query=message,
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="chat",
        )

        return create_response(
            data=response_data.dict(), message="Chat completed successfully"
        )

    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}", response_model=dict)
async def get_conversation_history(
    conversation_id: str, amazon_q: AmazonQServiceDep, config_valid: ConfigValidationDep
):
    """
    Retrieve conversation history for a given conversation ID.

    Note: This would require additional Amazon Q API methods for conversation management.
    For now, it returns a placeholder response.
    """
    try:
        # This would require additional Amazon Q API integration
        # For now, return a placeholder
        return create_response(
            data={
                "conversation_id": conversation_id,
                "status": "placeholder",
                "message": "Conversation history retrieval not yet implemented",
            },
            message="Conversation history placeholder",
        )

    except Exception as e:
        logger.error(f"Error retrieving conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# New specific service analysis endpoints


@router.post("/analyze/ec2", response_model=dict)
async def analyze_ec2_underutilization(
    amazon_q: AmazonQServiceDep,
    config_valid: ConfigValidationDep,
    time_range: str = "30d",
):
    """
    Analyze underutilized EC2 instances with detailed metrics.

    This endpoint specifically analyzes EC2 instances for:
    - Low CPU and memory utilization
    - Right-sizing opportunities
    - Cost optimization recommendations
    """
    try:
        logger.info(f"Analyzing EC2 underutilization for time range: {time_range}")

        result = await amazon_q.analyze_ec2_underutilization(time_range)

        response_data = AmazonQResponse(
            query=f"EC2 underutilization analysis for {time_range}",
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="ec2_analysis",
        )

        return create_response(
            data=response_data.dict(),
            message="EC2 underutilization analysis completed successfully",
        )

    except Exception as e:
        logger.error(f"Error in EC2 analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/ebs", response_model=dict)
async def analyze_ebs_underutilization(
    amazon_q: AmazonQServiceDep, config_valid: ConfigValidationDep
):
    """
    Analyze underutilized EBS volumes.

    This endpoint analyzes EBS volumes for:
    - Unattached volumes
    - Low I/O operations
    - Cost optimization opportunities
    """
    try:
        logger.info("Analyzing EBS underutilization")

        result = await amazon_q.analyze_ebs_underutilization()

        response_data = AmazonQResponse(
            query="EBS volumes underutilization analysis",
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="ebs_analysis",
        )

        return create_response(
            data=response_data.dict(),
            message="EBS underutilization analysis completed successfully",
        )

    except Exception as e:
        logger.error(f"Error in EBS analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/s3", response_model=dict)
async def analyze_s3_underutilization(
    amazon_q: AmazonQServiceDep, config_valid: ConfigValidationDep
):
    """
    Analyze underutilized S3 buckets.

    This endpoint analyzes S3 buckets for:
    - Empty or underused buckets
    - Storage class optimization
    - Access pattern analysis
    """
    try:
        logger.info("Analyzing S3 underutilization")

        result = await amazon_q.analyze_s3_underutilization()

        response_data = AmazonQResponse(
            query="S3 buckets underutilization analysis",
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="s3_analysis",
        )

        return create_response(
            data=response_data.dict(),
            message="S3 underutilization analysis completed successfully",
        )

    except Exception as e:
        logger.error(f"Error in S3 analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/lambda", response_model=dict)
async def analyze_lambda_underutilization(
    amazon_q: AmazonQServiceDep, config_valid: ConfigValidationDep
):
    """
    Analyze underutilized Lambda functions.

    This endpoint analyzes Lambda functions for:
    - Low invocation rates
    - Over-provisioned configurations
    - Cost optimization opportunities
    """
    try:
        logger.info("Analyzing Lambda underutilization")

        result = await amazon_q.analyze_lambda_underutilization()

        response_data = AmazonQResponse(
            query="Lambda functions underutilization analysis",
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="lambda_analysis",
        )

        return create_response(
            data=response_data.dict(),
            message="Lambda underutilization analysis completed successfully",
        )

    except Exception as e:
        logger.error(f"Error in Lambda analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/rds", response_model=dict)
async def analyze_rds_underutilization(
    amazon_q: AmazonQServiceDep, config_valid: ConfigValidationDep
):
    """
    Analyze underutilized RDS instances.

    This endpoint analyzes RDS instances for:
    - Low utilization metrics
    - Right-sizing opportunities
    - Cost optimization recommendations
    """
    try:
        logger.info("Analyzing RDS underutilization")

        result = await amazon_q.analyze_rds_underutilization()

        response_data = AmazonQResponse(
            query="RDS instances underutilization analysis",
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="rds_analysis",
        )

        return create_response(
            data=response_data.dict(),
            message="RDS underutilization analysis completed successfully",
        )

    except Exception as e:
        logger.error(f"Error in RDS analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/comprehensive", response_model=dict)
async def comprehensive_cost_analysis(
    amazon_q: AmazonQServiceDep,
    config_valid: ConfigValidationDep,
    services: List[str] = None,
):
    """
    Perform comprehensive cost optimization analysis across multiple AWS services.

    This endpoint analyzes multiple services for comprehensive cost optimization
    including EC2, EBS, S3, Lambda, RDS and provides prioritized recommendations.
    """
    try:
        services_list = services or ["EC2", "EBS", "S3", "Lambda", "RDS"]
        logger.info(f"Performing comprehensive analysis for services: {services_list}")

        result = await amazon_q.comprehensive_cost_analysis(services_list)

        response_data = AmazonQResponse(
            query=f"Comprehensive cost analysis for services: {', '.join(services_list)}",
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="comprehensive_analysis",
        )

        return create_response(
            data=response_data.dict(),
            message=f"Comprehensive cost analysis completed for {len(services_list)} services",
        )

    except Exception as e:
        logger.error(f"Error in comprehensive analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/for-dashboard", response_model=dict)
async def query_for_dashboard_creation(
    request: CostOptimizationQuery,
    amazon_q: AmazonQServiceDep,
    config_valid: ConfigValidationDep,
    services: List[str] = None,
):
    """
    Query Amazon Q specifically for dashboard creation with enhanced prompting.
    
    This endpoint explicitly tells Amazon Q that the output will be processed by another
    LLM system to create comprehensive cost optimization dashboards, resulting in more
    detailed, specific, and actionable data with exact resource identifiers and cost calculations.
    """
    try:
        services_list = services or ["EC2", "EBS", "S3", "Lambda", "RDS"]
        logger.info(f"Querying Amazon Q for dashboard creation: {request.query[:100]}...")
        logger.info(f"Services to analyze: {services_list}")

        # Use the new dashboard-specific query method
        result = await amazon_q.query_for_dashboard_creation(
            query=request.query,
            services=services_list
        )

        response_data = AmazonQResponse(
            query=f"Dashboard creation query for {', '.join(services_list)}: {request.query}",
            response=result["response"],
            conversation_id=result.get("conversation_id"),
            source_attributions=result.get("source_attributions", []),
            timestamp=datetime.utcnow().isoformat(),
            query_type="dashboard_creation",
        )

        return create_response(
            data=response_data.dict(),
            message=f"Dashboard-specific analysis completed for {len(services_list)} services with enhanced detail",
        )

    except Exception as e:
        logger.error(f"Error in dashboard creation query: {e}")
        raise HTTPException(status_code=500, detail=str(e))
