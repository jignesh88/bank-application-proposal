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


def regenerate_proposal(client_details: Dict[str, Any], financial_data: Dict[str, Any], 
                        context_result: Dict[str, Any], previous_attempt: Dict[str, Any]) -> Dict[str, Any]:
    """Regenerate a proposal with error corrections"""
    try:
        # Initialize OpenAI
        initialize_openai()
        
        # Extract error information from previous attempt
        error = previous_attempt.get('error', 'Unknown error')
        raw_proposal = previous_attempt.get('raw_proposal', {})
        
        # Create system message with error correction instructions
        system_message = """
        You are an expert financial advisor that creates detailed personalized wealth management proposals.
        The previous attempt to generate a proposal had errors that need to be fixed.
        Follow these rules:
        1. Fix all validation errors in the previous attempt
        2. Ensure all allocations add up to 100%
        3. Include appropriate risk disclaimers for each product
        4. Provide a clear implementation timeline
        5. Format your response as a valid JSON object matching the ProposalDocument schema
        """
        
        # Create prompt with client information, context, and error details
        user_message = f"""
        CLIENT INFORMATION:
        Name: {client_details.get('client_name', 'Unknown')}
        Type: {client_details.get('client_type', 'Unknown')}
        Risk Profile: {client_details.get('risk_profile', 'Unknown')}
        Investment Horizon: {client_details.get('investment_horizon', 'Unknown')} years
        Total Assets: ${client_details.get('total_assets', 0):,.2f}
        
        PREVIOUS ATTEMPT ERRORS:
        {error}
        
        PREVIOUS PROPOSAL:
        {json.dumps(raw_proposal, indent=2) if isinstance(raw_proposal, dict) else raw_proposal}
        
        Please fix the errors and create a valid proposal that matches the ProposalDocument schema.
        """
        
        # Generate corrected proposal
        response = openai.ChatCompletion.create(
            model=FINE_TUNED_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.2,
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
            
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Regenerated proposal still has errors: {e}")
            
            # Force a more structured approach on second failure
            return format_proposal_fallback(client_details, financial_data, context_result)
            
    except Exception as e:
        logger.error(f"Error regenerating proposal: {e}")
        return {
            'is_valid': False,
            'error': f"Error regenerating proposal: {str(e)}"
        }


def format_proposal_fallback(client_details: Dict[str, Any], financial_data: Dict[str, Any], 
                             context_result: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback method to generate a valid proposal with a more structured approach"""
    try:
        # Generate a minimal valid proposal structure
        proposal_id = f"PROP-{uuid.uuid4().hex[:8].upper()}"
        
        # Create a basic proposal with minimal required fields
        proposal = {
            "proposal_id": proposal_id,
            "generation_date": datetime.now().isoformat(),
            "client_details": {
                "client_id": client_details.get('client_id', f"C-{uuid.uuid4().hex[:6].upper()}"),
                "client_name": client_details.get('client_name', 'Unknown'),
                "client_type": client_details.get('client_type', 'individual'),
                "risk_profile": client_details.get('risk_profile', 'moderate'),
                "investment_horizon": client_details.get('investment_horizon', '10'),
                "total_assets": float(client_details.get('total_assets', 100000))
            },
            "executive_summary": "Custom wealth management proposal based on client's risk profile and investment goals.",
            "recommendations": [
                {
                    "product_name": "Diversified Equity Fund",
                    "product_type": "Mutual Fund",
                    "allocation_percentage": 40.0,
                    "expected_return": 7.5,
                    "risk_level": "Moderate",
                    "fee_structure": "1.2% annual management fee"
                },
                {
                    "product_name": "Corporate Bond Fund",
                    "product_type": "Fixed Income",
                    "allocation_percentage": 30.0,
                    "expected_return": 4.5,
                    "risk_level": "Low to Moderate",
                    "fee_structure": "0.8% annual management fee"
                },
                {
                    "product_name": "Money Market Fund",
                    "product_type": "Cash Equivalent",
                    "allocation_percentage": 15.0,
                    "expected_return": 2.0,
                    "risk_level": "Low",
                    "fee_structure": "0.5% annual management fee"
                },
                {
                    "product_name": "Real Estate Investment Trust",
                    "product_type": "Alternative Investment",
                    "allocation_percentage": 15.0,
                    "expected_return": 6.0,
                    "risk_level": "Moderate",
                    "fee_structure": "1.5% annual management fee"
                }
            ],
            "strategic_rationale": "This balanced portfolio is designed to provide a mix of growth and income while maintaining a moderate risk profile aligned with the client's investment horizon.",
            "implementation_timeline": "Week 1: Initial allocation of funds\nWeek 2-3: Phased investment into selected products\nWeek 4: Review and adjustments\nQuarterly: Regular portfolio reviews",
            "risk_disclaimers": [
                {
                    "disclaimer_id": "RISK-001",
                    "disclaimer_text": "Past performance is not indicative of future results. The value of investments can go down as well as up.",
                    "applicable_products": ["Diversified Equity Fund", "Corporate Bond Fund", "Real Estate Investment Trust"]
                },
                {
                    "disclaimer_id": "RISK-002",
                    "disclaimer_text": "Investments are not FDIC insured and may lose value.",
                    "applicable_products": ["Diversified Equity Fund", "Corporate Bond Fund", "Money Market Fund", "Real Estate Investment Trust"]
                }
            ]
        }
        
        # Validate with Pydantic
        validated_proposal = ProposalDocument(**proposal)
        
        return {
            'is_valid': True,
            'proposal': validated_proposal.dict(),
            'fallback_used': True
        }
            
    except Exception as e:
        logger.error(f"Error in fallback proposal generation: {e}")
        return {
            'is_valid': False,
            'error': f"Error in fallback proposal generation: {str(e)}"
        }


def format_document(proposal: Dict[str, Any], format_type: str = 'docx') -> Dict[str, Any]:
    """Format the proposal as a document"""
    try:
        proposal_id = proposal.get('proposal_id', f"PROP-{uuid.uuid4().hex[:8].upper()}")
        client_name = proposal.get('client_details', {}).get('client_name', 'Unknown')
        
        # Create a file name
        sanitized_client_name = ''.join(c if c.isalnum() else '_' for c in client_name)
        file_name = f"{sanitized_client_name}_{proposal_id}.{format_type}"
        s3_key = f"proposals/{file_name}"
        
        # For now, create a simple text/markdown representation
        # In a real implementation, this would use python-docx or similar library
        markdown_content = f"""# Investment Proposal for {client_name}
Proposal ID: {proposal_id}
Generation Date: {proposal.get('generation_date', datetime.now().isoformat())}

## Executive Summary
{proposal.get('executive_summary', '')}

## Client Profile
- **Name**: {proposal.get('client_details', {}).get('client_name', '')}
- **Type**: {proposal.get('client_details', {}).get('client_type', '')}
- **Risk Profile**: {proposal.get('client_details', {}).get('risk_profile', '')}
- **Investment Horizon**: {proposal.get('client_details', {}).get('investment_horizon', '')} years
- **Total Assets**: ${proposal.get('client_details', {}).get('total_assets', 0):,.2f}

## Investment Recommendations

| Product | Type | Allocation | Expected Return | Risk Level | Fee Structure |
|---------|------|------------|-----------------|------------|---------------|
"""
        
        # Add each recommendation to the table
        for rec in proposal.get('recommendations', []):
            markdown_content += f"| {rec.get('product_name', '')} | {rec.get('product_type', '')} | {rec.get('allocation_percentage', 0)}% | {rec.get('expected_return', 0)}% | {rec.get('risk_level', '')} | {rec.get('fee_structure', '')} |\n"
        
        # Add strategic rationale
        markdown_content += f"""
## Strategic Rationale
{proposal.get('strategic_rationale', '')}

## Implementation Timeline
{proposal.get('implementation_timeline', '')}

## Risk Disclaimers
"""
        
        # Add risk disclaimers
        for disc in proposal.get('risk_disclaimers', []):
            markdown_content += f"""
### {disc.get('disclaimer_id', '')}
{disc.get('disclaimer_text', '')}

Applicable to: {', '.join(disc.get('applicable_products', []))}
"""
        
        # Add additional notes if present
        if additional_notes := proposal.get('additional_notes'):
            markdown_content += f"""
## Additional Notes
{additional_notes}
"""
        
        # Upload to S3
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{format_type}') as tmp:
            tmp.write(markdown_content)
            tmp.flush()
            
            s3.upload_file(
                Filename=tmp.name,
                Bucket=PROPOSALS_BUCKET,
                Key=s3_key
            )
        
        # Generate a pre-signed URL for downloading
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': PROPOSALS_BUCKET,
                'Key': s3_key
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        
        return {
            'proposal_id': proposal_id,
            'file_name': file_name,
            's3_key': s3_key,
            'download_url': presigned_url,
            'format_type': format_type
        }
        
    except Exception as e:
        logger.error(f"Error formatting document: {e}")
        raise


def handler(event, context):
    """Lambda handler function"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Determine operation type
        operation = event.get('operation')
        
        if operation == 'generate_proposal':
            # Generate a proposal
            client_details = event.get('client_details', {})
            financial_data = event.get('financial_data', {})
            context_result = event.get('context_result', {})
            model = event.get('model')
            
            result = generate_proposal(client_details, financial_data, context_result, model)
            return {
                'statusCode': 200,
                'proposal_result': result
            }
            
        elif operation == 'regenerate_proposal':
            # Regenerate a proposal that had validation errors
            client_details = event.get('client_details', {})
            financial_data = event.get('financial_data', {})
            context_result = event.get('context_result', {})
            previous_attempt = event.get('previous_attempt', {})
            
            result = regenerate_proposal(client_details, financial_data, context_result, previous_attempt)
            return {
                'statusCode': 200,
                'proposal_result': result
            }
            
        elif operation == 'format_document':
            # Format the proposal as a document
            proposal = event.get('proposal', {})
            format_type = event.get('format_type', 'docx')
            
            result = format_document(proposal, format_type)
            return {
                'statusCode': 200,
                'document_result': result
            }
            
        else:
            logger.error(f"Unknown operation: {operation}")
            return {
                'statusCode': 400,
                'error': f"Unknown operation: {operation}"
            }
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'error': str(e)
        }