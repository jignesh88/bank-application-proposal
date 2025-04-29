import os
import json
import boto3
import logging
import tempfile
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("document_processor")

# Initialize AWS clients
s3 = boto3.client('s3')
textract = boto3.client('textract')
ssm = boto3.client('ssm')
comprehend = boto3.client('comprehend')

# Get environment variables
TEMPLATES_BUCKET = os.environ.get('TEMPLATES_BUCKET')
PROPOSALS_BUCKET = os.environ.get('PROPOSALS_BUCKET')
OPENAI_API_KEY_PARAM = os.environ.get('OPENAI_API_KEY_PARAM')


def extract_text_with_textract(bucket_name: str, object_key: str) -> str:
    """Extract text from a document using AWS Textract"""
    try:
        # For synchronous processing of small documents
        response = textract.detect_document_text(
            Document={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': object_key
                }
            }
        )
        
        # Extract text blocks
        text = ""
        for item in response['Blocks']:
            if item['BlockType'] == 'LINE':
                text += item['Text'] + "\n"
                
        logger.info(f"Successfully extracted text from {object_key}")
        return text
        
    except Exception as e:
        logger.error(f"Error extracting text from {object_key}: {e}")
        raise


def start_textract_job(bucket_name: str, object_key: str) -> str:
    """Start an asynchronous Textract job for larger documents"""
    try:
        response = textract.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': object_key
                }
            },
            NotificationChannel={
                'SNSTopicArn': os.environ.get('TEXTRACT_SNS_TOPIC'),
                'RoleArn': os.environ.get('TEXTRACT_ROLE_ARN')
            }
        )
        
        job_id = response['JobId']
        logger.info(f"Started Textract job {job_id} for {object_key}")
        return job_id
        
    except Exception as e:
        logger.error(f"Error starting Textract job for {object_key}: {e}")
        raise


def process_document(document_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process an uploaded document"""
    document_type = document_data.get('document_type')
    s3_key = document_data.get('s3_key')
    document_name = document_data.get('document_name', Path(s3_key).stem)
    
    if not s3_key or not document_type:
        raise ValueError("Missing required fields: document_type or s3_key")
    
    # Extract text based on document type
    if document_type in ['pdf', 'docx', 'doc']:
        text = extract_text_with_textract(TEMPLATES_BUCKET, s3_key)
        
        # Analyze entities if requested
        entities = []
        if document_data.get('analyze_entities', False):
            entity_response = comprehend.detect_entities(
                Text=text[:5000],  # Limit to first 5000 chars due to API limits
                LanguageCode='en'
            )
            entities = entity_response.get('Entities', [])
            
        return {
            'document_id': document_name,
            'document_type': document_type,
            's3_key': s3_key,
            'text_content': text,
            'entities': entities,
            'processed_timestamp': datetime.now().isoformat()
        }
        
    elif document_type in ['xlsx', 'xls', 'csv']:
        # For spreadsheets, we don't extract text but process the structured data
        with tempfile.NamedTemporaryFile(suffix=f'.{document_type}') as tmp:
            s3.download_file(TEMPLATES_BUCKET, s3_key, tmp.name)
            
            if document_type == 'csv':
                df = pd.read_csv(tmp.name)
            else:
                df = pd.read_excel(tmp.name)
                
            # Basic metadata about the spreadsheet
            return {
                'document_id': document_name,
                'document_type': document_type,
                's3_key': s3_key,
                'column_names': df.columns.tolist(),
                'row_count': len(df),
                'has_missing_values': df.isnull().any().any(),
                'processed_timestamp': datetime.now().isoformat()
            }
    else:
        raise ValueError(f"Unsupported document type: {document_type}")


def handler(event, context):
    """Lambda handler function"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Determine operation type
        operation = event.get('operation')
        
        if operation == 'process_documents':
            # Process multiple documents
            documents = event.get('documents', [])
            results = []
            
            for doc in documents:
                result = process_document(doc)
                results.append(result)
                
            return {
                'statusCode': 200,
                'processed_documents': results
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