import os
import json
import boto3
import logging
import base64
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_handler")

# Initialize AWS clients
s3 = boto3.client('s3')
sfn = boto3.client('stepfunctions')

# Get environment variables
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')
TEMPLATES_BUCKET = os.environ.get('TEMPLATES_BUCKET')


def start_workflow(workflow_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Start a Step Functions workflow of the specified type"""
    try:
        # Validate workflow type
        valid_types = ['document_ingestion', 'fine_tuning', 'proposal_generation']
        if workflow_type not in valid_types:
            raise ValueError(f"Invalid workflow type: {workflow_type}. Valid types are: {', '.join(valid_types)}")
            
        # Add workflow type to the payload
        full_payload = {
            'workflow_type': workflow_type,
            **payload
        }
        
        # Start execution
        response = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"{workflow_type}-{uuid.uuid4()}",
            input=json.dumps(full_payload)
        )
        
        logger.info(f"Started {workflow_type} workflow with execution ARN: {response['executionArn']}")
        
        return {
            'execution_arn': response['executionArn'],
            'started_at': response['startDate'].isoformat(),
            'workflow_type': workflow_type
        }
        
    except Exception as e:
        logger.error(f"Error starting workflow: {e}")
        raise


def handle_document_upload(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle document upload requests"""
    try:
        # Check if the request contains a base64-encoded file
        if 'file_content_base64' not in body:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing file_content_base64 in request'
                })
            }
            
        # Extract file information
        file_content_base64 = body['file_content_base64']
        file_name = body.get('file_name', f"document-{uuid.uuid4()}")
        document_type = body.get('document_type', 'pdf')
        
        # Decode the file content
        file_content = base64.b64decode(file_content_base64)
        
        # Upload to S3
        s3_key = f"templates/{file_name}"
        s3.put_object(
            Bucket=TEMPLATES_BUCKET,
            Key=s3_key,
            Body=file_content
        )
        
        logger.info(f"Uploaded file to s3://{TEMPLATES_BUCKET}/{s3_key}")
        
        # Start document ingestion workflow
        workflow_result = start_workflow('document_ingestion', {
            'documents': [{
                'document_type': document_type,
                's3_key': s3_key,
                'document_name': file_name
            }]
        })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f"Document uploaded successfully: {file_name}",
                'document_type': document_type,
                's3_key': s3_key,
                'workflow_execution': workflow_result
            })
        }
        
    except Exception as e:
        logger.error(f"Error handling document upload: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }