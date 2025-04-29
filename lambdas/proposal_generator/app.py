import os
import json
import boto3
import logging
import tempfile
import uuid
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("proposal_generator")

# Initialize AWS clients
s3 = boto3.client('s3')
ssm = boto3.client('ssm')

# Get environment variables
PROPOSALS_BUCKET = os.environ.get('PROPOSALS_BUCKET')
VECTOR_STORE_BUCKET = os.environ.get('VECTOR_STORE_BUCKET')
OPENAI_API_KEY_PARAM = os.environ.get('OPENAI_API_KEY_PARAM')
FINE_TUNED_MODEL = os.environ.get('FINE_TUNED_MODEL', 'gpt-4-turbo')

# Import OpenAI and pydantic for validation
import openai
from pydantic import BaseModel, Field, validator, root_validator, ValidationError
from typing import List, Dict, Any, Optional
from datetime import datetime

# Pydantic Models for Validation

class ClientDetails(BaseModel):
    """Client information schema"""
    client_id: str = Field(..., description="Unique identifier for the client")
    client_name: str = Field(..., description="Full name of the client")
    client_type: str = Field(..., description="Type of client (individual, corporate, etc.)")
    risk_profile: str = Field(..., description="Client's risk profile (conservative, moderate, aggressive)")
    investment_horizon: str = Field(..., description="Client's investment time horizon in years")
    total_assets: float = Field(..., description="Total client assets under management")
    
    @validator('total_assets')
    def validate_total_assets(cls, value):
        if value < 0:
            raise ValueError("Total assets cannot be negative")
        return value


class ProductRecommendation(BaseModel):
    """Schema for product recommendations"""
    product_name: str = Field(..., description="Name of the financial product")
    product_type: str = Field(..., description="Category of the product")
    allocation_percentage: float = Field(..., description="Percentage allocation in the portfolio")
    expected_return: float = Field(..., description="Expected annual return percentage")
    risk_level: str = Field(..., description="Risk level of the product")
    fee_structure: str = Field(..., description="Fee structure description")
    
    @validator('allocation_percentage')
    def validate_allocation(cls, value):
        if not 0 <= value <= 100:
            raise ValueError("Allocation percentage must be between 0 and 100")
        return value


class RiskDisclaimer(BaseModel):
    """Schema for risk disclaimers"""
    disclaimer_id: str = Field(..., description="Unique identifier for the disclaimer")
    disclaimer_text: str = Field(..., description="Full text of the disclaimer")
    applicable_products: List[str] = Field(..., description="Products this disclaimer applies to")
    regulatory_references: List[str] = Field([], description="Regulatory references for this disclaimer")


class ProposalDocument(BaseModel):
    """Complete proposal document schema"""
    proposal_id: str = Field(..., description="Unique identifier for the proposal")
    generation_date: datetime = Field(default_factory=datetime.now)
    client_details: ClientDetails
    executive_summary: str = Field(..., description="Executive summary of the proposal")
    recommendations: List[ProductRecommendation]
    strategic_rationale: str = Field(..., description="Rationale for the proposed strategy")
    implementation_timeline: str = Field(..., description="Timeline for implementing the proposal")
    risk_disclaimers: List[RiskDisclaimer]
    additional_notes: Optional[str] = None
    
    @root_validator
    def validate_total_allocation(cls, values):
        if "recommendations" in values:
            total_allocation = sum(rec.allocation_percentage for rec in values["recommendations"])
            if not (99.5 <= total_allocation <= 100.5):  # Allow small rounding errors
                raise ValueError(f"Total allocation must equal 100% (current: {total_allocation}%)")
        return values