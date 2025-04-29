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


# Set up OpenAI API key
def get_openai_api_key():
    """Retrieve OpenAI API key from Parameter Store"""
    try:
        response = ssm.get_parameter(
            Name=OPENAI_API_KEY_PARAM,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"Error retrieving OpenAI API key: {e}")
        raise


def initialize_openai():
    """Initialize OpenAI API client"""
    openai.api_key = get_openai_api_key()


def generate_proposal(client_details: Dict[str, Any], financial_data: Dict[str, Any], context_result: Dict[str, Any], model: str = None) -> Dict[str, Any]:
    """Generate a proposal using the fine-tuned model and RAG context"""
    try:
        # Initialize OpenAI
        initialize_openai()
        
        # Use specified model or default to the configured fine-tuned model
        model_to_use = model or FINE_TUNED_MODEL
        
        # Extract relevant context
        context_items = context_result.get('body', {}).get('context', [])
        context_text = "\n\n".join([item['content'] for item in context_items]) if context_items else ""
        
        # Create system message with instructions
        system_message = """
        You are an expert financial advisor that creates detailed personalized wealth management proposals.
        Follow these rules:
        1. Use the client information and context to create a tailored proposal
        2. Ensure all allocations add up to 100%
        3. Include appropriate risk disclaimers for each product
        4. Provide a clear implementation timeline
        5. Format your response as a valid JSON object matching the ProposalDocument schema
        """
        
        # Create prompt with client information and context
        user_message = f"""
        CLIENT INFORMATION:
        Name: {client_details.get('client_name', 'Unknown')}
        Type: {client_details.get('client_type', 'Unknown')}
        Risk Profile: {client_details.get('risk_profile', 'Unknown')}
        Investment Horizon: {client_details.get('investment_horizon', 'Unknown')} years
        Total Assets: ${client_details.get('total_assets', 0):,.2f}
        
        FINANCIAL DATA SUMMARY:
        {json.dumps(financial_data.get('validation_result', {}).get('summary_statistics', {}), indent=2)}
        
        RELEVANT CONTEXT:
        {context_text}
        
        Please create a comprehensive wealth management proposal for this client.
        Your output must be a valid JSON object that matches the ProposalDocument schema.
        """
        
        # Generate proposal using OpenAI
        response = openai.ChatCompletion.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        # Extract generated proposal
        proposal_text = response.choices[0].message.content
        
        # Try to parse as JSON
        try:
            proposal_json = json.loads(proposal_text)
            
            # If proposal_id is not provided, generate one
            if 'proposal_id' not in proposal_json:
                proposal_json['proposal_id'] = f"PROP-{uuid.uuid4().hex[:8].upper()}"
                
            # Validate with Pydantic
            proposal = ProposalDocument(**proposal_json)
            
            return {
                'is_valid': True,
                'proposal': proposal.dict(),
                'usage': response.usage.to_dict() if hasattr(response, 'usage') else None
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Generated proposal is not valid JSON: {e}")
            return {
                'is_valid': False,
                'error': f"Generated proposal is not valid JSON: {str(e)}",
                'raw_proposal': proposal_text
            }
            
        except ValidationError as e:
            logger.error(f"Generated proposal failed schema validation: {e}")
            return {
                'is_valid': False,
                'error': f"Schema validation failed: {str(e)}",
                'raw_proposal': proposal_json
            }
            
    except Exception as e:
        logger.error(f"Error generating proposal: {e}")
        return {
            'is_valid': False,
            'error': f"Error generating proposal: {str(e)}"
        }