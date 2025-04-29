import os
import json
import boto3
import logging
import tempfile
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_pipeline")

# Initialize AWS clients
s3 = boto3.client('s3')
ssm = boto3.client('ssm')

# Get environment variables
TEMPLATES_BUCKET = os.environ.get('TEMPLATES_BUCKET')
VECTOR_STORE_BUCKET = os.environ.get('VECTOR_STORE_BUCKET')
OPENAI_API_KEY_PARAM = os.environ.get('OPENAI_API_KEY_PARAM')

# Import OpenAI and other dependencies
import openai
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

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


def create_text_chunks(documents: List[Dict[str, Any]]) -> List[Document]:
    """Split documents into chunks suitable for embedding"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    
    langchain_docs = []
    
    for doc in documents:
        # Skip if document doesn't have text content
        if 'text_content' not in doc:
            continue
            
        # Create a LangChain Document
        langchain_doc = Document(
            page_content=doc['text_content'],
            metadata={
                'document_id': doc.get('document_id', ''),
                'document_type': doc.get('document_type', ''),
                's3_key': doc.get('s3_key', '')
            }
        )
        
        langchain_docs.append(langchain_doc)
    
    # Split into chunks
    chunks = text_splitter.split_documents(langchain_docs)
    logger.info(f"Created {len(chunks)} text chunks from {len(langchain_docs)} documents")
    
    return chunks


def save_vector_store(vector_store, vector_store_path: str):
    """Save the vector store to S3"""
    try:
        # Save to local temp directory first
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "vector_store"
            vector_store.save_local(str(local_path))
            
            # Upload to S3
            for file_path in local_path.glob('**/*'):
                if file_path.is_file():
                    relative_path = file_path.relative_to(local_path)
                    s3_key = f"{vector_store_path}/{relative_path}"
                    
                    s3.upload_file(
                        Filename=str(file_path),
                        Bucket=VECTOR_STORE_BUCKET,
                        Key=s3_key
                    )
            
        logger.info(f"Vector store saved to s3://{VECTOR_STORE_BUCKET}/{vector_store_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving vector store: {e}")
        raise


def load_vector_store(vector_store_path: str, embeddings):
    """Load a vector store from S3"""
    try:
        # Create a temporary directory to download the vector store
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "vector_store"
            local_path.mkdir(exist_ok=True)
            
            # List files in the S3 vector store directory
            paginator = s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=VECTOR_STORE_BUCKET,
                Prefix=vector_store_path
            )
            
            # Download all files
            for page in pages:
                if 'Contents' not in page:
                    raise FileNotFoundError(f"Vector store not found at {vector_store_path}")
                    
                for obj in page['Contents']:
                    s3_key = obj['Key']
                    relative_path = s3_key[len(vector_store_path)+1:]  # +1 for the slash
                    local_file_path = local_path / relative_path
                    
                    # Create directory if it doesn't exist
                    local_file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Download file
                    s3.download_file(
                        Bucket=VECTOR_STORE_BUCKET,
                        Key=s3_key,
                        Filename=str(local_file_path)
                    )
            
            # Load the vector store from the local path
            vector_store = FAISS.load_local(str(local_path), embeddings)
            logger.info(f"Vector store loaded from {vector_store_path}")
            
            return vector_store
            
    except FileNotFoundError:
        logger.warning(f"Vector store not found at {vector_store_path}")
        return None
    except Exception as e:
        logger.error(f"Error loading vector store: {e}")
        raise


def ingest_documents(processed_documents: List[Dict[str, Any]], vector_store_path: str = "default_vector_store") -> Dict[str, Any]:
    """Ingest documents into the vector store"""
    try:
        # Initialize OpenAI
        initialize_openai()
        
        # Create embeddings instance
        embeddings = OpenAIEmbeddings()
        
        # Create text chunks
        chunks = create_text_chunks(processed_documents)
        
        if not chunks:
            return {
                'success': False,
                'error': 'No valid text content found in documents'
            }
        
        # Try to load existing vector store
        vector_store = load_vector_store(vector_store_path, embeddings)
        
        if vector_store:
            # Add new documents to existing vector store
            vector_store.add_documents(chunks)
            logger.info(f"Added {len(chunks)} chunks to existing vector store")
        else:
            # Create new vector store
            vector_store = FAISS.from_documents(chunks, embeddings)
            logger.info(f"Created new vector store with {len(chunks)} chunks")
        
        # Save updated vector store
        save_vector_store(vector_store, vector_store_path)
        
        return {
            'success': True,
            'chunks_count': len(chunks),
            'vector_store_path': vector_store_path
        }
        
    except Exception as e:
        logger.error(f"Error ingesting documents: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def retrieve_context(query: str, client_details: Dict[str, Any], vector_store_path: str = "default_vector_store", k: int = 5) -> Dict[str, Any]:
    """Retrieve relevant context for a query"""
    try:
        # Initialize OpenAI
        initialize_openai()
        
        # Create embeddings instance
        embeddings = OpenAIEmbeddings()
        
        # Load vector store
        vector_store = load_vector_store(vector_store_path, embeddings)
        
        if not vector_store:
            return {
                'success': False,
                'error': f"Vector store not found at {vector_store_path}"
            }
        
        # Enhance query with client details for better retrieval
        enhanced_query = f"Client: {client_details.get('client_name', '')}, " + \
                         f"Type: {client_details.get('client_type', '')}, " + \
                         f"Risk Profile: {client_details.get('risk_profile', '')}, " + \
                         f"Investment Horizon: {client_details.get('investment_horizon', '')} years. " + \
                         f"{query}"
        
        # Retrieve relevant documents
        docs_and_scores = vector_store.similarity_search_with_score(enhanced_query, k=k)
        
        # Format results
        results = []
        for doc, score in docs_and_scores:
            results.append({
                'content': doc.page_content,
                'metadata': doc.metadata,
                'relevance_score': float(score)  # Convert numpy float to native float
            })
        
        return {
            'success': True,
            'context': results,
            'query': enhanced_query
        }
        
    except Exception as e:
        logger.error(f"Error retrieving context: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def handler(event, context):
    """Lambda handler function"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Determine operation type
        operation = event.get('operation')
        
        if operation == 'ingest_documents':
            # Ingest documents into vector store
            processed_documents = event.get('processed_documents', {}).get('processed_documents', [])
            vector_store_path = event.get('vector_store_path', 'default_vector_store')
            
            result = ingest_documents(processed_documents, vector_store_path)
            return {
                'statusCode': 200 if result['success'] else 500,
                'body': result
            }
            
        elif operation == 'retrieve_context':
            # Retrieve context for proposal generation
            client_details = event.get('client_details', {})
            query = event.get('query', '')
            vector_store_path = event.get('vector_store_path', 'default_vector_store')
            k = event.get('k', 5)
            
            if not query:
                # If no explicit query provided, create one from client details
                query = f"Generate wealth management proposal for {client_details.get('client_name', 'client')}"
            
            result = retrieve_context(query, client_details, vector_store_path, k)
            return {
                'statusCode': 200 if result['success'] else 500,
                'body': result
            }
            
        else:
            logger.error(f"Unknown operation: {operation}")
            return {
                'statusCode': 400,
                'body': {
                    'success': False,
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
                'success': False,
                'error': str(e)
            }
        }