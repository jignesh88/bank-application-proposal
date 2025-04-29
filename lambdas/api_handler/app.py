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


def handle_fine_tuning_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle fine-tuning requests"""
    try:
        # Check if historic proposals key is provided
        if 'historic_proposals_key' not in body:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing historic_proposals_key in request'
                })
            }
            
        historic_proposals_key = body['historic_proposals_key']
        model_name = body.get('model_name', 'gpt-4-turbo')
        
        # Start fine-tuning workflow
        workflow_result = start_workflow('fine_tuning', {
            'historic_proposals_key': historic_proposals_key,
            'model_name': model_name
        })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Fine-tuning job started successfully',
                'historic_proposals_key': historic_proposals_key,
                'model_name': model_name,
                'workflow_execution': workflow_result
            })
        }
        
    except Exception as e:
        logger.error(f"Error handling fine-tuning request: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


def handle_proposal_generation(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle proposal generation requests"""
    try:
        # Check for required fields
        required_fields = ['client_details', 'financial_data_key']
        missing_fields = [field for field in required_fields if field not in body]
        
        if missing_fields:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f"Missing required fields: {', '.join(missing_fields)}"
                })
            }
            
        # Extract request parameters
        client_details = body['client_details']
        financial_data_key = body['financial_data_key']
        
        # Additional validation parameters
        required_columns = body.get('required_columns', [])
        critical_columns = body.get('critical_columns', [])
        amount_columns = body.get('amount_columns', [])
        allocation_column = body.get('allocation_column')
        
        # Prepare the payload
        payload = {
            'client_details': client_details,
            'financial_data': {
                'financial_data_key': financial_data_key,
                'required_columns': required_columns,
                'critical_columns': critical_columns,
                'amount_columns': amount_columns,
                'allocation_column': allocation_column
            }
        }
        
        # Start proposal generation workflow
        workflow_result = start_workflow('proposal_generation', payload)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Proposal generation started successfully',
                'client_name': client_details.get('client_name', 'Unknown'),
                'workflow_execution': workflow_result
            })
        }
        
    except Exception as e:
        logger.error(f"Error handling proposal generation request: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


def handle_status_check(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle workflow status check requests"""
    try:
        # Extract the execution ARN from query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        execution_arn = query_params.get('execution_arn')
        
        if not execution_arn:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing execution_arn parameter'
                })
            }
            
        # Check execution status
        response = sfn.describe_execution(
            executionArn=execution_arn
        )
        
        status = response['status']
        output = json.loads(response.get('output', '{}')) if 'output' in response else None
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_arn': execution_arn,
                'status': status,
                'started_at': response['startDate'].isoformat(),
                'stopped_at': response.get('stopDate', '').isoformat() if 'stopDate' in response else None,
                'output': output
            })
        }
        
    except Exception as e:
        logger.error(f"Error checking workflow status: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


def handler(event, context):
    """Lambda handler function"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Determine the request type
        http_method = event.get('httpMethod', '')
        resource = event.get('resource', '')
        
        # Parse the request body if present
        body = {}
        if 'body' in event and event['body']:
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Invalid JSON in request body'
                    })
                }
                
        # Route the request
        if resource == '/workflow' and http_method == 'POST':
            # Check workflow type
            if 'workflow_type' not in body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Missing workflow_type in request'
                    })
                }
                
            workflow_type = body['workflow_type']
            
            if workflow_type == 'document_ingestion':
                return handle_document_upload(body)
                
            elif workflow_type == 'fine_tuning':
                return handle_fine_tuning_request(body)
                
            elif workflow_type == 'proposal_generation':
                return handle_proposal_generation(body)
                
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': f"Invalid workflow_type: {workflow_type}"
                    })
                }
                
        elif resource == '/status' and http_method == 'GET':
            return handle_status_check(event)
            
        elif resource == '/documents' and http_method == 'POST':
            return handle_document_upload(body)
            
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'error': f"Unsupported resource or method: {resource} {http_method}"
                })
            }
            
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }