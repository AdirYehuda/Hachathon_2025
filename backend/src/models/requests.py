import re
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class CostOptimizationQuery(BaseModel):
    query: str = Field(
        ..., min_length=10, max_length=1000, description="Cost optimization query"
    )
    time_range: Optional[str] = Field(
        "30d", description="Time range for analysis (e.g., '30d', '7d', '90d')"
    )
    resource_types: List[str] = Field(
        default=[], description="Specific resource types to analyze"
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        # Remove potentially dangerous characters
        if re.search(r'[<>"\']', v):
            raise ValueError("Query contains invalid characters")
        return v.strip()

    @field_validator("time_range")
    @classmethod
    def validate_time_range(cls, v):
        if v and not re.match(r"^\d+[dhwmy]$", v):
            raise ValueError(
                "Time range must be in format like '30d', '7d', '1w', '1m', '1y'"
            )
        return v


class UnderutilizationQuery(BaseModel):
    resource_type: str = Field(
        ..., description="Type of resource to analyze (e.g., 'EC2', 'RDS', 'S3')"
    )
    time_range: Optional[str] = Field("30d", description="Time range for analysis")
    utilization_threshold: Optional[float] = Field(
        20.0, ge=0, le=100, description="Utilization threshold percentage"
    )

    @field_validator("resource_type")
    @classmethod
    def validate_resource_type(cls, v):
        allowed_types = [
            "EC2",
            "RDS",
            "S3",
            "EBS",
            "Lambda",
            "ELB",
            "CloudFront",
            "ElastiCache",
        ]
        if v.upper() not in allowed_types:
            raise ValueError(
                f"Resource type must be one of: {', '.join(allowed_types)}"
            )
        return v.upper()


class BedrockProcessingRequest(BaseModel):
    data_objects: List[Dict] = Field(
        ..., min_length=1, description="List of data objects to process"
    )
    processing_type: str = Field(
        ...,
        description="Type of processing to perform",
    )
    agent_id: Optional[str] = Field(
        None, description="Override default Bedrock agent ID"
    )
    agent_alias_id: Optional[str] = Field(
        None, description="Override default Bedrock agent alias ID"
    )

    @field_validator("data_objects")
    @classmethod
    def validate_data_objects(cls, v):
        for i, obj in enumerate(v):
            if not isinstance(obj, dict) or not obj:
                raise ValueError(
                    f"Data object at index {i} must be a non-empty dictionary"
                )
        return v

    @field_validator("processing_type")
    @classmethod
    def validate_processing_type(cls, v):
        allowed_types = ["summary", "analysis", "report", "dashboard_summary"]
        if v not in allowed_types:
            raise ValueError(f"Processing type must be one of: {', '.join(allowed_types)}")
        return v


class DashboardGenerationRequest(BaseModel):
    summary_data: Dict = Field(
        ..., description="Processed summary data for dashboard generation"
    )
    dashboard_type: str = Field(
        "cost_optimization",
        description="Type of dashboard to generate",
    )
    dashboard_name: Optional[str] = Field(
        "costAnalysis", max_length=50, description="Custom name for the dashboard"
    )
    title: Optional[str] = Field(
        None, max_length=100, description="Custom dashboard title"
    )
    embed_options: Optional[Dict] = Field(
        default={}, description="Options for embed code generation"
    )

    @field_validator("summary_data")
    @classmethod
    def validate_summary_data(cls, v):
        if not isinstance(v, dict) or not v:
            raise ValueError("Summary data must be a non-empty dictionary")
        return v

    @field_validator("dashboard_type")
    @classmethod
    def validate_dashboard_type(cls, v):
        allowed_types = ["cost_optimization", "utilization", "general"]
        if v not in allowed_types:
            raise ValueError(f"Dashboard type must be one of: {', '.join(allowed_types)}")
        return v

    @field_validator("embed_options")
    @classmethod
    def validate_embed_options(cls, v):
        if v:
            allowed_keys = ["width", "height", "frameborder", "allowfullscreen"]
            for key in v.keys():
                if key not in allowed_keys:
                    raise ValueError(
                        f"Invalid embed option: {key}. Allowed: {', '.join(allowed_keys)}"
                    )
        return v

    @field_validator("dashboard_name")
    @classmethod
    def validate_dashboard_name(cls, v):
        if v:
            # Remove invalid characters for use in URLs/filenames
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', v):
                raise ValueError("Dashboard name can only contain letters, numbers, underscores, and dashes")
        return v or "costAnalysis"


class MultiStepWorkflowRequest(BaseModel):
    """Complete workflow request combining all steps"""

    amazon_q_queries: List[Union[CostOptimizationQuery, UnderutilizationQuery]] = Field(
        ..., min_items=1, description="List of Amazon Q queries to execute"
    )
    processing_type: str = Field(
        "analysis",
        description="Bedrock processing type",
    )
    dashboard_config: Optional[Dict] = Field(
        default={}, description="Dashboard generation configuration"
    )

    @field_validator("amazon_q_queries")
    @classmethod
    def validate_queries(cls, v):
        if len(v) > 10:
            raise ValueError("Maximum 10 queries allowed per workflow")
        return v

    @field_validator("processing_type")
    @classmethod
    def validate_processing_type_workflow(cls, v):
        allowed_types = ["summary", "analysis", "report", "dashboard_summary"]
        if v not in allowed_types:
            raise ValueError(f"Processing type must be one of: {', '.join(allowed_types)}")
        return v


class BulkDataProcessingRequest(BaseModel):
    """For processing multiple data objects in bulk"""

    data_objects: List[Dict] = Field(
        ..., min_length=1, max_length=50, description="Bulk data objects to process"
    )
    batch_size: Optional[int] = Field(
        5, ge=1, le=10, description="Number of objects to process per batch"
    )
    processing_options: Optional[Dict] = Field(
        default={}, description="Additional processing options"
    )

    @field_validator("data_objects")
    @classmethod
    def validate_bulk_data(cls, v):
        total_size = sum(len(str(obj)) for obj in v)
        if total_size > 1000000:  # 1MB limit
            raise ValueError("Total data size exceeds 1MB limit")
        return v


class DashboardSummaryRequest(BaseModel):
    """Request model for creating dashboard summary from processed data"""

    processed_data: str = Field(
        ..., description="Processed data from Bedrock analysis to create dashboard summary from"
    )
    agent_id: Optional[str] = Field(
        None, description="Override default Bedrock agent ID"
    )
    agent_alias_id: Optional[str] = Field(
        None, description="Override default Bedrock agent alias ID"
    )

    @field_validator("processed_data")
    @classmethod
    def validate_processed_data(cls, v):
        if not v.strip():
            raise ValueError("Processed data cannot be empty")
        return v.strip()
