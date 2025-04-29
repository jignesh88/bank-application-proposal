import os
import json
import boto3
import logging
import tempfile
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fine_tuning")

# Initialize AWS clients
s3 = boto3.client('s3')
ssm = boto3.client('ssm')
dynamodb = boto3.resource('dynamodb')

# Get environment variables
TEMPLATES_BUCKET = os.environ.get('TEMPLATES_BUCKET')
OPENAI_API_KEY_PARAM = os.environ.get('OPENAI_API_KEY_PARAM')
FINE_TUNING_TABLE = os.environ.get('FINE_TUNING_TABLE', 'BankingProposalFineTuning')

# Import OpenAI
import openai

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


def prepare_training_data(historic_proposals: List[Dict[str, Any]], output_file: str = "training_data.jsonl") -> str:
    """Prepare training data for fine-tuning"""
    try:
        training_examples = []
        
        for proposal in historic_proposals:
            # Create a system message
            system_message = "You are an expert financial advisor that creates detailed personalized proposals."
            
            # Create a user message (input)
            client_details = proposal.get('client_details', {})
            user_message = f"""
            CLIENT INFORMATION:
            Name: {client_details.get('client_name', 'Unknown')}
            Type: {client_details.get('client_type', 'Unknown')}
            Risk Profile: {client_details.get('risk_profile', 'Unknown')}
            Investment Horizon: {client_details.get('investment_horizon', 'Unknown')} years
            Total Assets: ${client_details.get('total_assets', 0):,.2f}
            
            Please create a comprehensive wealth management proposal for this client.
            """
            
            # Create an assistant message (expected output)
            # This would typically be the proposal document in JSON format
            assistant_message = json.dumps(proposal.get('document', {}))
            
            # Create the training example
            example = {
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_message}
                ]
            }
            
            training_examples.append(example)
        
        # Write to JSONL file
        with open(output_file, 'w') as f:
            for example in training_examples:
                f.write(json.dumps(example) + '\n')
                
        logger.info(f"Prepared {len(training_examples)} training examples in {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error preparing training data: {e}")
        raise


def start_fine_tuning_job(training_file_path: str, model_name: str = "gpt-4-turbo") -> Dict[str, Any]:
    """Start a fine-tuning job with OpenAI"""
    try:
        # Initialize OpenAI
        initialize_openai()
        
        # Upload the file to OpenAI
        with open(training_file_path, 'rb') as f:
            file_response = openai.File.create(
                file=f,
                purpose='fine-tune'
            )
            
        file_id = file_response.id
        logger.info(f"Uploaded training file with ID: {file_id}")
        
        # Create fine-tuning job
        job_response = openai.FineTuningJob.create(
            training_file=file_id,
            model=model_name,
            suffix="banking-proposal-generator"
        )
        
        job_id = job_response.id
        logger.info(f"Started fine-tuning job with ID: {job_id}")
        
        # Store job information in DynamoDB for tracking
        table = dynamodb.Table(FINE_TUNING_TABLE)
        
        table.put_item(
            Item={
                'job_id': job_id,
                'file_id': file_id,
                'model': model_name,
                'status': job_response.status,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'training_examples_count': sum(1 for _ in open(training_file_path))
            }
        )
        
        return {
            'job_id': job_id,
            'file_id': file_id,
            'status': job_response.status,
            'model': model_name
        }
        
    except Exception as e:
        logger.error(f"Error starting fine-tuning job: {e}")
        raise


def check_fine_tuning_status(job_id: str) -> Dict[str, Any]:
    """Check the status of a fine-tuning job"""
    try:
        # Initialize OpenAI
        initialize_openai()
        
        # Retrieve job status
        job_response = openai.FineTuningJob.retrieve(job_id)
        
        # Update status in DynamoDB
        table = dynamodb.Table(FINE_TUNING_TABLE)
        
        table.update_item(
            Key={'job_id': job_id},
            UpdateExpression="SET #status = :status, updated_at = :updated_at, fine_tuned_model = :model, trained_tokens = :tokens",
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': job_response.status,
                ':updated_at': datetime.now().isoformat(),
                ':model': job_response.get('fine_tuned_model', ''),
                ':tokens': job_response.get('trained_tokens', 0)
            }
        )
        
        return {
            'job_id': job_id,
            'status': job_response.status,
            'fine_tuned_model': job_response.get('fine_tuned_model', ''),
            'trained_tokens': job_response.get('trained_tokens', 0),
            'completed_at': job_response.get('completed_at', ''),
            'error': job_response.get('error', None)
        }
        
    except Exception as e:
        logger.error(f"Error checking fine-tuning status: {e}")
        raise


def prepare_and_start_fine_tuning(historic_proposals_key: str, model_name: str = "gpt-4-turbo") -> Dict[str, Any]:
    """Download historic proposals, prepare training data, and start fine-tuning"""
    try:
        # Download historic proposals file
        with tempfile.NamedTemporaryFile(suffix='.json') as proposals_file:
            s3.download_file(
                Bucket=TEMPLATES_BUCKET,
                Key=historic_proposals_key,
                Filename=proposals_file.name
            )
            
            # Load historic proposals
            with open(proposals_file.name, 'r') as f:
                historic_proposals = json.load(f)
        
        # Prepare training data
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as training_file:
            training_file_path = training_file.name
        
        prepare_training_data(historic_proposals, training_file_path)
        
        # Start fine-tuning job
        result = start_fine_tuning_job(training_file_path, model_name)
        
        # Clean up temporary file
        os.unlink(training_file_path)
        
        return result
        
    except Exception as e:
        logger.error(f"Error preparing and starting fine-tuning: {e}")
        raise


def handler(event, context):
    """Lambda handler function"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Determine operation type
        operation = event.get('operation')
        
        if operation == 'prepare_and_start_fine_tuning':
            # Prepare training data and start fine-tuning
            historic_proposals_key = event.get('historic_proposals_key')
            model_name = event.get('model_name', 'gpt-4-turbo')
            
            if not historic_proposals_key:
                return {
                    'statusCode': 400,
                    'body': {
                        'error': 'Missing historic_proposals_key parameter'
                    }
                }
            
            result = prepare_and_start_fine_tuning(historic_proposals_key, model_name)
            return {
                'statusCode': 200,
                'body': result
            }
            
        elif operation == 'check_fine_tuning_status':
            # Check status of a fine-tuning job
            job_id = event.get('job_id')
            
            if not job_id:
                return {
                    'statusCode': 400,
                    'body': {
                        'error': 'Missing job_id parameter'
                    }
                }
            
            result = check_fine_tuning_status(job_id)
            return {
                'statusCode': 200,
                'body': result
            }
            
        else:
            logger.error(f"Unknown operation: {operation}")
            return {
                'statusCode': 400,
                'body': {
                    'error': f"Unknown operation: {operation}"
                }
            }
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': {
                'error': str(e)
            }
        }