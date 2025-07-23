import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

from src.api.dependencies import BedrockServiceDep, ConfigValidationDep
from src.core.config import settings
from src.models.requests import (BedrockProcessingRequest,
                                 BulkDataProcessingRequest,
                                 DashboardSummaryRequest)
from src.models.responses import BedrockProcessingResponse, create_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bedrock", tags=["Bedrock Processing"])


@router.post("/process", response_model=dict)
async def process_data_objects(
    request: BedrockProcessingRequest,
    bedrock: BedrockServiceDep,
    config_valid: ConfigValidationDep,
):
    """
    Process multiple data objects through Bedrock agent.

    This endpoint takes multiple JSON data objects and processes them through
    a Bedrock agent to create a comprehensive analysis and summary.
    """
    try:
        logger.info(
            f"Processing {len(request.data_objects)} data objects with type: {request.processing_type}"
        )

        # Use provided agent IDs or fall back to settings
        agent_id = request.agent_id or settings.bedrock_agent_id
        agent_alias_id = request.agent_alias_id or settings.bedrock_agent_alias_id

        if not agent_id:
            raise HTTPException(
                status_code=500, detail="Bedrock agent ID not configured"
            )

        # Process data objects through Bedrock agent
        result = await bedrock.process_data_objects(
            data_objects=request.data_objects,
            agent_id=agent_id,
            agent_alias_id=agent_alias_id,
        )

        # Create response
        response_data = BedrockProcessingResponse(
            processed_data=result["response"],
            processing_type=request.processing_type,
            session_id=f"session-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow().isoformat(),
            metadata={
                "input_objects_count": len(request.data_objects),
                "agent_id": agent_id,
                "agent_alias_id": agent_alias_id,
            },
        )

        return create_response(
            data=response_data.dict(),
            message=f"Successfully processed {len(request.data_objects)} data objects",
        )

    except Exception as e:
        logger.error(f"Error in Bedrock processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/debug-dashboard-summary", response_model=dict)
async def debug_dashboard_summary(request: Request):
    """Debug endpoint to see raw request body"""
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        logger.info(f"DEBUG - Raw request body: {body}")
        logger.info(f"DEBUG - Content-Type: {content_type}")

        if content_type.startswith("application/json"):
            try:
                import json
                parsed = json.loads(body)
                logger.info(f"DEBUG - Parsed JSON: {parsed}")
            except Exception as e:
                logger.error(f"DEBUG - JSON parse error: {e}")

        return {"status": "debug", "body_length": len(body), "content_type": content_type}
    except Exception as e:
        logger.error(f"DEBUG - Error: {e}")
        return {"status": "error", "error": str(e)}

# Add exception handler for validation errors
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error for {request.url}: {exc}")
    logger.error(f"Request body: {await request.body()}")
    logger.error(f"Request headers: {dict(request.headers)}")
    logger.error(f"Validation details: {exc.errors()}")

    # Return the default error response
    return await request_validation_exception_handler(request, exc)

@router.post("/raw-dashboard-summary")
async def raw_dashboard_summary(request: Request):
    """Raw endpoint to see exactly what's being sent"""
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        
        logger.info(f"RAW REQUEST - URL: {request.url}")
        logger.info(f"RAW REQUEST - Method: {request.method}")
        logger.info(f"RAW REQUEST - Headers: {dict(request.headers)}")
        logger.info(f"RAW REQUEST - Body: {body}")
        logger.info(f"RAW REQUEST - Content-Type: {content_type}")
        
        if content_type.startswith("application/json"):
            try:
                import json
                parsed = json.loads(body)
                logger.info(f"RAW REQUEST - Parsed JSON: {parsed}")
                logger.info(f"RAW REQUEST - Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'Not a dict'}")
                
                # Check each field
                if isinstance(parsed, dict):
                    for key, value in parsed.items():
                        logger.info(f"RAW REQUEST - Field '{key}': type={type(value).__name__}, value={repr(value)}")
                        
            except Exception as e:
                logger.error(f"RAW REQUEST - JSON parse error: {e}")
        
        return {"status": "raw_intercepted", "body_length": len(body)}
    except Exception as e:
        logger.error(f"RAW REQUEST - Error: {e}")
        return {"status": "error", "error": str(e)}

@router.post("/create-dashboard-summary", response_model=dict)
async def create_dashboard_summary(
    request: DashboardSummaryRequest,
    bedrock: BedrockServiceDep,
    config_valid: ConfigValidationDep,
):
    """
    Create dashboard-ready summary from processed data.

    This endpoint takes processed data and creates a structured summary
    optimized for dashboard visualization.
    """
    try:
        logger.info(f"Creating dashboard summary - processed_data length: {len(request.processed_data)}, agent_id: {request.agent_id}, agent_alias_id: {request.agent_alias_id}")

        # Use provided agent IDs or fall back to settings
        agent_id = request.agent_id or settings.bedrock_agent_id
        agent_alias_id = request.agent_alias_id or settings.bedrock_agent_alias_id

        if not agent_id:
            raise HTTPException(
                status_code=500, detail="Bedrock agent ID not configured"
            )

        # Create dashboard summary
        result = await bedrock.create_dashboard_summary(
            processed_data=request.processed_data,
            agent_id=agent_id,
            agent_alias_id=agent_alias_id,
        )

        # Try to parse the response as JSON for structured data
        try:
            parsed_response = json.loads(result["response"])
        except (json.JSONDecodeError, KeyError):
            parsed_response = result["response"]

        # Create response
        response_data = BedrockProcessingResponse(
            processed_data=parsed_response,
            processing_type="dashboard_summary",
            session_id=f"dashboard-session-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow().isoformat(),
            metadata={
                "agent_id": agent_id,
                "agent_alias_id": agent_alias_id,
                "is_structured": isinstance(parsed_response, dict),
            },
        )

        return create_response(
            data=response_data.dict(), message="Dashboard summary created successfully"
        )

    except ValidationError as ve:
        logger.error(f"Validation error in dashboard summary: {ve}")
        raise HTTPException(status_code=422, detail=f"Validation error: {ve}")
    except Exception as e:
        logger.error(f"Error creating dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-process", response_model=dict)
async def bulk_process_data(
    request: BulkDataProcessingRequest,
    background_tasks: BackgroundTasks,
    bedrock: BedrockServiceDep,
    config_valid: ConfigValidationDep,
):
    """
    Process multiple data objects in bulk with batching.

    This endpoint handles large volumes of data by processing them in batches
    and can be run asynchronously for better performance.
    """
    try:
        logger.info(f"Starting bulk processing of {len(request.data_objects)} objects")

        # For now, process synchronously in batches
        # In production, you might want to use Celery or similar for async processing

        batch_size = request.batch_size
        data_objects = request.data_objects
        results = []

        # Process in batches
        for i in range(0, len(data_objects), batch_size):
            batch = data_objects[i : i + batch_size]
            logger.info(
                f"Processing batch {i // batch_size + 1} with {len(batch)} objects"
            )

            # Create processing request for this batch
            batch_request = BedrockProcessingRequest(
                data_objects=batch, processing_type="analysis"
            )

            # Process batch
            result = await bedrock.process_data_objects(
                data_objects=batch,
                agent_id=settings.bedrock_agent_id,
                agent_alias_id=settings.bedrock_agent_alias_id,
            )

            results.append(
                {
                    "batch_number": i // batch_size + 1,
                    "objects_processed": len(batch),
                    "result": result["response"],
                }
            )

        # Create consolidated response
        response_data = {
            "total_objects": len(data_objects),
            "total_batches": len(results),
            "batch_size": batch_size,
            "batch_results": results,
            "processing_options": request.processing_options,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return create_response(
            data=response_data,
            message=f"Bulk processing completed: {len(data_objects)} objects in {len(results)} batches",
        )

    except Exception as e:
        logger.error(f"Error in bulk processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/status", response_model=dict)
async def get_session_status(
    session_id: str, bedrock: BedrockServiceDep, config_valid: ConfigValidationDep
):
    """
    Get the status of a Bedrock processing session.

    Note: This is a placeholder endpoint. In a real implementation,
    you would track session states in a database or cache.
    """
    try:
        # This would require session state management
        # For now, return a placeholder response
        return create_response(
            data={
                "session_id": session_id,
                "status": "placeholder",
                "message": "Session status tracking not yet implemented",
            },
            message="Session status placeholder",
        )

    except Exception as e:
        logger.error(f"Error retrieving session status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
