import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.api.dependencies import (AmazonQServiceDep, BedrockServiceDep,
                                  ConfigValidationDep, DashboardServiceDep,
                                  S3ServiceDep)
from src.models.requests import (DashboardGenerationRequest,
                                 MultiStepWorkflowRequest)
from src.models.responses import (DashboardResponse, WorkflowResponse,
                                  create_response)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.post("/generate", response_model=dict)
async def generate_dashboard(
    request: DashboardGenerationRequest,
    dashboard_service: DashboardServiceDep,
    s3_service: S3ServiceDep,
    config_valid: ConfigValidationDep,
):
    """
    Generate dashboard from summary data and deploy to S3.

    This endpoint takes processed summary data and creates an interactive
    dashboard with charts and visualizations, then deploys it to S3 for
    static web hosting.
    """
    try:
        logger.info(f"Generating {request.dashboard_type} dashboard")

        # Generate dashboard HTML
        dashboard_html = await dashboard_service.create_dashboard(
            summary_data=request.summary_data, 
            dashboard_type=request.dashboard_type,
            dashboard_name=request.dashboard_name
        )

        # Generate unique site ID with readable timestamp
        readable_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dashboard_name = request.dashboard_name or "costAnalysis"
        site_id = f"{dashboard_name}_{readable_timestamp}"

        # Get additional static assets
        static_assets = dashboard_service.get_static_assets()

        # Upload to S3
        public_url = await s3_service.upload_static_site(
            html_content=dashboard_html, site_id=site_id, additional_files=static_assets
        )

        # Create embed code
        embed_options = request.embed_options or {}
        width = embed_options.get("width", "100%")
        height = embed_options.get("height", "600px")
        embed_code = await s3_service.create_embed_code(public_url, width, height)

        # Create response
        response_data = DashboardResponse(
            dashboard_url=public_url,
            site_id=site_id,
            embed_code=embed_code,
            dashboard_type=request.dashboard_type,
            timestamp=datetime.utcnow().isoformat(),
            title=request.title,
            metadata={
                "embed_options": embed_options,
                "static_assets_count": len(static_assets),
            },
        )

        return create_response(
            data=response_data.dict(),
            message=f"Dashboard generated and deployed successfully to {public_url}",
        )

    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow/complete", response_model=dict)
async def complete_workflow(
    request: MultiStepWorkflowRequest,
    amazon_q: AmazonQServiceDep,
    bedrock: BedrockServiceDep,
    dashboard_service: DashboardServiceDep,
    s3_service: S3ServiceDep,
    config_valid: ConfigValidationDep,
):
    """
    Execute complete workflow: Amazon Q queries → Bedrock processing → Dashboard generation.

    This endpoint executes the complete workflow:
    1. Runs multiple Amazon Q queries for cost optimization and underutilization
    2. Processes results through Bedrock agent for comprehensive analysis
    3. Generates and deploys interactive dashboard to S3
    """
    start_time = datetime.utcnow()
    workflow_id = f"workflow-{uuid.uuid4().hex[:8]}"

    # Log workflow start
    logger.info("=" * 80)
    logger.info("🚀 STARTING COMPLETE WORKFLOW")
    logger.info("=" * 80)
    logger.info(f"🆔 Workflow ID: {workflow_id}")
    logger.info(f"📊 Number of queries: {len(request.amazon_q_queries)}")
    logger.info(f"🎯 Processing type: {request.processing_type}")
    logger.info(f"📅 Start time: {start_time}")
    
    # Log each query that will be processed
    for i, query in enumerate(request.amazon_q_queries):
        logger.info(f"🔍 Query {i+1}: {getattr(query, 'query', 'N/A')[:100]}...")
        if hasattr(query, 'resource_types'):
            logger.info(f"   Resource types: {getattr(query, 'resource_types', [])}")
    logger.info("=" * 80)

    try:
        logger.info(
            f"Starting complete workflow {workflow_id} with {len(request.amazon_q_queries)} queries"
        )

        # Step 1: Execute Amazon Q queries
        logger.info("📤 STEP 1: EXECUTING AMAZON Q QUERIES")
        logger.info("-" * 50)
        
        amazon_q_results = []
        for i, query in enumerate(request.amazon_q_queries):
            logger.info(f"Processing query {i+1}/{len(request.amazon_q_queries)}")

            if hasattr(query, "query"):  # CostOptimizationQuery
                # Check if specific resource types are selected
                if hasattr(query, "resource_types") and query.resource_types:
                    # Process each resource type specifically
                    for resource_type in query.resource_types:
                        logger.info(f"Processing specific resource type: {resource_type}")
                        
                        # Call the specific analysis endpoint based on resource type
                        if resource_type.upper() == "EC2":
                            result = await amazon_q.analyze_ec2_underutilization(query.time_range or "30d")
                            query_type = "ec2_analysis"
                            original_query = f"EC2 underutilization analysis - {query.query}"
                        elif resource_type.upper() == "EBS":
                            result = await amazon_q.analyze_ebs_underutilization()
                            query_type = "ebs_analysis"
                            original_query = f"EBS underutilization analysis - {query.query}"
                        elif resource_type.upper() == "S3":
                            result = await amazon_q.analyze_s3_underutilization()
                            query_type = "s3_analysis"
                            original_query = f"S3 underutilization analysis - {query.query}"
                        elif resource_type.upper() == "LAMBDA":
                            result = await amazon_q.analyze_lambda_underutilization()
                            query_type = "lambda_analysis"
                            original_query = f"Lambda underutilization analysis - {query.query}"
                        elif resource_type.upper() == "RDS":
                            result = await amazon_q.analyze_rds_underutilization()
                            query_type = "rds_analysis"
                            original_query = f"RDS underutilization analysis - {query.query}"
                        else:
                            # Fallback to general cost optimization for other resource types
                            result = await amazon_q.query_cost_optimization(f"{query.query} - Focus on {resource_type}")
                            query_type = "cost_optimization"
                            original_query = f"{resource_type} cost optimization - {query.query}"

                        # Log the result from Amazon Q with detailed debugging
                        logger.info(f"✅ Query completed for {resource_type}")
                        logger.info(f"🔍 WORKFLOW DEBUG - Amazon Q Result Structure:")
                        logger.info(f"   Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                        logger.info(f"   Result type: {type(result)}")
                        if isinstance(result, dict):
                            response_content = result.get('response', 'NO_RESPONSE_KEY')
                            logger.info(f"   Response type: {type(response_content)}")
                            logger.info(f"   Response length: {len(response_content) if isinstance(response_content, str) else 'Not a string'}")
                            if isinstance(response_content, str) and response_content:
                                logger.info(f"   Response preview: {response_content[:200]}...")
                            else:
                                logger.info(f"   Response content: {repr(response_content)}")
                        else:
                            logger.info(f"   Raw result: {repr(result)}")

                        amazon_q_results.append({
                            "query": original_query,
                            "response": result["response"],
                            "conversation_id": result.get("conversation_id"),
                            "source_attributions": result.get("source_attributions", []),
                            "timestamp": datetime.utcnow().isoformat(),
                            "query_type": query_type,
                            "resource_type": resource_type.upper(),
                        })
                else:
                    # No specific resource types selected, use general cost optimization
                    result = await amazon_q.query_cost_optimization(query.query)
                    query_type = "cost_optimization"
                    original_query = query.query
                    
                    logger.info(f"✅ General cost optimization query completed")
                    logger.info(f"🔍 WORKFLOW DEBUG - General Cost Optimization Result:")
                    logger.info(f"   Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                    if isinstance(result, dict):
                        response_content = result.get('response', 'NO_RESPONSE_KEY')
                        logger.info(f"   Response length: {len(response_content) if isinstance(response_content, str) else 'Not a string'}")
                        if isinstance(response_content, str) and response_content:
                            logger.info(f"   Response preview: {response_content[:200]}...")
                        else:
                            logger.info(f"   Response content: {repr(response_content)}")
                    else:
                        logger.info(f"   Raw result: {repr(result)}")
                    
                    amazon_q_results.append({
                        "query": original_query,
                        "response": result["response"],
                        "conversation_id": result.get("conversation_id"),
                        "source_attributions": result.get("source_attributions", []),
                        "timestamp": datetime.utcnow().isoformat(),
                        "query_type": query_type,
                    })
            else:  # UnderutilizationQuery
                result = await amazon_q.query_underutilization(
                    resource_type=query.resource_type, time_range=query.time_range
                )
                query_type = "underutilization"
                original_query = f"Underutilization analysis for {query.resource_type}"
                
                logger.info(f"✅ Underutilization query completed for {query.resource_type}")
                logger.info(f"🔍 WORKFLOW DEBUG - Underutilization Result:")
                logger.info(f"   Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                if isinstance(result, dict):
                    response_content = result.get('response', 'NO_RESPONSE_KEY')
                    logger.info(f"   Response length: {len(response_content) if isinstance(response_content, str) else 'Not a string'}")
                    if isinstance(response_content, str) and response_content:
                        logger.info(f"   Response preview: {response_content[:200]}...")
                    else:
                        logger.info(f"   Response content: {repr(response_content)}")
                else:
                    logger.info(f"   Raw result: {repr(result)}")
                
                amazon_q_results.append({
                    "query": original_query,
                    "response": result["response"],
                    "conversation_id": result.get("conversation_id"),
                    "source_attributions": result.get("source_attributions", []),
                    "timestamp": datetime.utcnow().isoformat(),
                    "query_type": query_type,
                })

        logger.info(f"📊 Completed {len(amazon_q_results)} Amazon Q queries")
        logger.info(f"📏 Total response content: {sum(len(r['response']) for r in amazon_q_results)} characters")

        # Step 2: Process through Bedrock agent
        logger.info("🤖 STEP 2: PROCESSING THROUGH BEDROCK AGENT")
        logger.info("-" * 50)
        
        # Using existing agent from settings to avoid spinning up new ones
        bedrock_result = await bedrock.process_data_objects(
            data_objects=amazon_q_results,
            agent_id=None,  # Use existing agent from settings.bedrock_agent_id
            agent_alias_id=None,  # Use existing alias from settings.bedrock_agent_alias_id
        )

        logger.info("✅ Bedrock processing completed")
        logger.info(f"📏 Bedrock response length: {len(bedrock_result['response'])} characters")

        # Step 3: Create dashboard summary optimized for React static serving
        logger.info("📊 STEP 3: CREATING DASHBOARD SUMMARY")
        logger.info("-" * 50)
        
        dashboard_summary_result = await bedrock.create_dashboard_summary(
            processed_data=bedrock_result["response"],
            agent_id=None,  # Reuse existing agent - no new agent creation
            agent_alias_id=None,  # Reuse existing alias
        )

        # Try to parse dashboard summary as JSON
        try:
            if isinstance(dashboard_summary_result["response"], str):
                summary_data = json.loads(dashboard_summary_result["response"])
            else:
                summary_data = dashboard_summary_result["response"]
                
            logger.info("✅ Dashboard summary parsed as JSON successfully")
            logger.info(f"📊 Summary keys: {list(summary_data.keys()) if isinstance(summary_data, dict) else 'Not a dict'}")
                
        except (json.JSONDecodeError, KeyError):
            # If parsing fails, create a basic structure
            logger.warning("⚠️ Dashboard summary JSON parsing failed, using fallback structure")
            summary_data = {
                "executive_summary": dashboard_summary_result["response"],
                "recommendations": [],
                "key_metrics": {},
                "cost_savings": {},
            }

        # Step 4: Generate dashboard
        logger.info("🎨 STEP 4: GENERATING DASHBOARD")
        logger.info("-" * 50)
        
        dashboard_config = request.dashboard_config or {}
        dashboard_type = dashboard_config.get("type", "cost_optimization")

        dashboard_html = await dashboard_service.create_dashboard(
            summary_data=summary_data, 
            dashboard_type=dashboard_type,
            dashboard_name=dashboard_name
        )

        # Deploy to S3 with human-readable naming
        readable_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dashboard_name = dashboard_config.get("dashboard_name", "costAnalysis")
        site_id = f"{dashboard_name}_{readable_timestamp}"
        static_assets = dashboard_service.get_static_assets()

        public_url = await s3_service.upload_static_site(
            html_content=dashboard_html, site_id=site_id, additional_files=static_assets
        )

        embed_code = await s3_service.create_embed_code(public_url)

        # Calculate execution time
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()

        logger.info("🎉 WORKFLOW COMPLETED SUCCESSFULLY!")
        logger.info("=" * 80)
        logger.info(f"🆔 Workflow ID: {workflow_id}")
        logger.info(f"📊 Dashboard Name: {site_id}")
        logger.info(f"⏱️ Total execution time: {execution_time:.2f} seconds")
        logger.info(f"🌐 Dashboard URL: {public_url}")
        logger.info(f"📊 Amazon Q queries: {len(amazon_q_results)}")
        logger.info(f"🤖 Bedrock processing: ✅")
        logger.info(f"📈 Dashboard generation: ✅")
        logger.info("=" * 80)

        # Create comprehensive response
        response_data = WorkflowResponse(
            workflow_id=workflow_id,
            amazon_q_results=[
                {
                    "query": result["query"],
                    "response": result["response"],
                    "conversation_id": result.get("conversation_id"),
                    "source_attributions": result.get("source_attributions", []),
                    "timestamp": result["timestamp"],
                    "query_type": result["query_type"],
                }
                for result in amazon_q_results
            ],
            bedrock_processing={
                "processed_data": bedrock_result["response"],
                "processing_type": request.processing_type,
                "session_id": f"session-{workflow_id}",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"input_queries_count": len(amazon_q_results)},
            },
            dashboard={
                "dashboard_url": public_url,
                "site_id": site_id,
                "embed_code": embed_code,
                "dashboard_type": dashboard_type,
                "timestamp": datetime.utcnow().isoformat(),
                "title": f"Cost Analysis Dashboard - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "metadata": dashboard_config,
            },
            total_execution_time=execution_time,
            timestamp=end_time.isoformat(),
            status="completed",
        )

        logger.info(
            f"Workflow {workflow_id} completed successfully in {execution_time:.2f} seconds"
        )
        
        return create_response(
            data=response_data.dict(),
            message=f"Cost Analysis Dashboard '{site_id}' generated successfully. Available at: {public_url}",
        )

    except Exception as e:
        logger.error("❌ WORKFLOW FAILED!")
        logger.error("=" * 80)
        logger.error(f"🆔 Workflow ID: {workflow_id}")
        logger.error(f"❌ Error: {str(e)}")
        logger.error(f"🕐 Failed at: {datetime.utcnow()}")
        logger.error("=" * 80)
        
        # Log full traceback for debugging
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=dict)
async def list_dashboards(s3_service: S3ServiceDep, config_valid: ConfigValidationDep):
    """
    List all deployed dashboards.

    This endpoint returns a list of all dashboards that have been
    deployed to S3 static hosting.
    """
    try:
        logger.info("Retrieving list of deployed dashboards")

        dashboards = await s3_service.list_dashboards()

        return create_response(
            data={
                "dashboards": dashboards,
                "total_count": len(dashboards),
                "timestamp": datetime.utcnow().isoformat(),
            },
            message=f"Retrieved {len(dashboards)} deployed dashboards",
        )

    except Exception as e:
        logger.error(f"Error listing dashboards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{site_id}/embed-code", response_model=dict)
async def get_embed_code(
    site_id: str,
    s3_service: S3ServiceDep,
    config_valid: ConfigValidationDep,
    width: str = "100%",
    height: str = "600px",
):
    """
    Get embed code for a specific dashboard.

    This endpoint generates embed code for a deployed dashboard
    with customizable width and height options.
    """
    try:
        logger.info(f"Generating embed code for dashboard {site_id}")

        # Construct dashboard URL
        if s3_service.use_website_endpoint:
            dashboard_url = f"https://{s3_service.bucket_name}.s3-website-{s3_service.region}.amazonaws.com/{site_id}/index.html"
        else:
            dashboard_url = f"https://{s3_service.bucket_name}.s3.{s3_service.region}.amazonaws.com/{site_id}/index.html"

        # Generate embed code
        embed_code = await s3_service.create_embed_code(dashboard_url, width, height)

        return create_response(
            data={
                "site_id": site_id,
                "dashboard_url": dashboard_url,
                "embed_code": embed_code,
                "width": width,
                "height": height,
                "timestamp": datetime.utcnow().isoformat(),
            },
            message="Embed code generated successfully",
        )

    except Exception as e:
        logger.error(f"Error generating embed code: {e}")
        raise HTTPException(status_code=500, detail=str(e))
