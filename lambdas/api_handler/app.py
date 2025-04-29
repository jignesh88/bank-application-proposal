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