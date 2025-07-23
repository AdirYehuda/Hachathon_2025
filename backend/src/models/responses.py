from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AmazonQResponse(BaseModel):
    query: str = Field(..., description="Original query")
    response: str = Field(..., description="Amazon Q response")
    conversation_id: Optional[str] = Field(
        None, description="Conversation ID for follow-up queries"
    )
    source_attributions: List[Dict] = Field(
        default=[], description="Source attributions from Amazon Q"
    )
    timestamp: str = Field(..., description="Response timestamp")
    query_type: str = Field(
        ..., description="Type of query (cost_optimization, underutilization)"
    )


class BedrockProcessingResponse(BaseModel):
    processed_data: Union[str, Dict] = Field(
        ..., description="Processed data from Bedrock agent"
    )
    processing_type: str = Field(..., description="Type of processing performed")
    session_id: str = Field(..., description="Bedrock session ID")
    timestamp: str = Field(..., description="Processing timestamp")
    metadata: Optional[Dict] = Field(
        default={}, description="Additional processing metadata"
    )


class DashboardResponse(BaseModel):
    dashboard_url: str = Field(..., description="Public URL of the deployed dashboard")
    site_id: str = Field(..., description="Unique site identifier")
    embed_code: str = Field(..., description="HTML embed code for the dashboard")
    dashboard_type: str = Field(..., description="Type of dashboard generated")
    timestamp: str = Field(..., description="Generation timestamp")
    title: Optional[str] = Field(None, description="Dashboard title")
    metadata: Optional[Dict] = Field(default={}, description="Dashboard metadata")


class WorkflowResponse(BaseModel):
    """Complete workflow response"""

    workflow_id: str = Field(..., description="Unique workflow identifier")
    amazon_q_results: List[AmazonQResponse] = Field(
        ..., description="Results from Amazon Q queries"
    )
    bedrock_processing: BedrockProcessingResponse = Field(
        ..., description="Bedrock processing results"
    )
    dashboard: DashboardResponse = Field(
        ..., description="Generated dashboard information"
    )
    total_execution_time: float = Field(
        ..., description="Total workflow execution time in seconds"
    )
    timestamp: str = Field(..., description="Workflow completion timestamp")
    status: str = Field("completed", description="Workflow status")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict] = Field(default={}, description="Additional error details")
    timestamp: str = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Service health status")
    timestamp: str = Field(..., description="Health check timestamp")
    services: Dict[str, str] = Field(..., description="Status of dependent services")
    version: str = Field(..., description="API version")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")


class DashboardListResponse(BaseModel):
    dashboards: List[Dict] = Field(..., description="List of available dashboards")
    total_count: int = Field(..., description="Total number of dashboards")
    timestamp: str = Field(..., description="Response timestamp")


class MetricsResponse(BaseModel):
    """API metrics and usage statistics"""

    total_queries: int = Field(..., description="Total number of queries processed")
    total_dashboards: int = Field(
        ..., description="Total number of dashboards generated"
    )
    average_response_time: float = Field(
        ..., description="Average response time in seconds"
    )
    success_rate: float = Field(..., description="Success rate percentage")
    timestamp: str = Field(..., description="Metrics timestamp")
    period: str = Field(..., description="Metrics period (e.g., '24h', '7d')")


class AsyncTaskResponse(BaseModel):
    """Response for asynchronous task submission"""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field("submitted", description="Task status")
    estimated_completion: Optional[str] = Field(
        None, description="Estimated completion time"
    )
    check_url: str = Field(..., description="URL to check task status")
    timestamp: str = Field(..., description="Task submission timestamp")


class TaskStatusResponse(BaseModel):
    """Response for task status check"""

    task_id: str = Field(..., description="Task identifier")
    status: str = Field(..., description="Current task status")
    progress: Optional[float] = Field(
        None, ge=0, le=100, description="Task progress percentage"
    )
    result: Optional[Union[WorkflowResponse, Dict]] = Field(
        None, description="Task result if completed"
    )
    error: Optional[ErrorResponse] = Field(None, description="Error details if failed")
    started_at: str = Field(..., description="Task start timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    estimated_completion: Optional[str] = Field(
        None, description="Estimated completion time"
    )


class ValidationErrorResponse(BaseModel):
    """Response for validation errors"""

    error: str = Field("validation_error", description="Error type")
    message: str = Field(..., description="Main error message")
    field_errors: List[Dict[str, Any]] = Field(
        ..., description="Field-specific validation errors"
    )
    timestamp: str = Field(..., description="Error timestamp")


class SuccessResponse(BaseModel):
    """Generic success response"""

    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success message")
    data: Optional[Dict] = Field(default={}, description="Response data")
    timestamp: str = Field(..., description="Response timestamp")


# Utility function to create standardized responses
def create_response(data: Any, message: str = "Success") -> Dict:
    """Create a standardized API response"""
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }


def create_error_response(
    error_type: str, message: str, details: Optional[Dict] = None
) -> ErrorResponse:
    """Create a standardized error response"""
    return ErrorResponse(
        error=error_type,
        message=message,
        details=details or {},
        timestamp=datetime.utcnow().isoformat(),
    )
