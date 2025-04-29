import unittest
import json
import os
import sys
import boto3
import tempfile
import numpy as np
from unittest.mock import patch, MagicMock, mock_open

# Add the lambda function directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'rag_pipeline'))
import app

class TestRAGPipeline(unittest.TestCase):
    """Test cases for the RAG Pipeline Lambda"""
    
    @patch('app.get_openai_api_key')
    def test_initialize_openai(self, mock_get_api_key):
        # Set up the mock
        mock_get_api_key.return_value = 'mock-api-key'
        
        # Call the function
        app.initialize_openai()
        
        # Check that the API key was set
        self.assertEqual(app.openai.api_key, 'mock-api-key')
        
    @patch('app.RecursiveCharacterTextSplitter')
    def test_create_text_chunks(self, mock_splitter_class):
        # Set up the mock
        mock_splitter = MagicMock()
        mock_splitter_class.return_value = mock_splitter
        mock_splitter.split_documents.return_value = ['chunk1', 'chunk2']
        
        # Test data
        documents = [
            {
                'document_id': 'doc1',
                'document_type': 'pdf',
                's3_key': 'test1.pdf',
                'text_content': 'Document 1 content'
            },
            {
                'document_id': 'doc2',
                'document_type': 'docx',
                's3_key': 'test2.docx',
                'text_content': 'Document 2 content'
            }
        ]
        
        # Call the function
        result = app.create_text_chunks(documents)
        
        # Check the result
        self.assertEqual(result, ['chunk1', 'chunk2'])
        
        # Verify that the splitter was called correctly
        self.assertEqual(mock_splitter.split_documents.call_count, 1)
        
    @patch('app.s3')
    @patch('app.tempfile.TemporaryDirectory')
    @patch('app.Path')
    def test_save_vector_store(self, mock_path, mock_temp_dir, mock_s3):
        # Set up mocks
        mock_vector_store = MagicMock()
        mock_temp_dir_instance = MagicMock()
        mock_temp_dir_instance.__enter__.return_value = '/tmp/vector_store'
        mock_temp_dir.return_value = mock_temp_dir_instance
        
        # Setup Path mock to return list of files
        mock_local_path = MagicMock()
        mock_path.return_value = mock_local_path
        mock_file1 = MagicMock()
        mock_file1.is_file.return_value = True
        mock_file1.relative_to.return_value = 'file1.txt'
        mock_local_path.glob.return_value = [mock_file1]
        
        # Call function
        result = app.save_vector_store(mock_vector_store, 'test_vector_store')
        
        # Check result
        self.assertTrue(result)
        
        # Verify vector store was saved
        mock_vector_store.save_local.assert_called_once_with('/tmp/vector_store')
        
        # Verify files were uploaded to S3
        mock_s3.upload_file.assert_called_once()
    
    @patch('app.get_openai_api_key')
    @patch('app.OpenAIEmbeddings')
    @patch('app.FAISS')
    @patch('app.create_text_chunks')
    @patch('app.save_vector_store')
    def test_ingest_documents(self, mock_save, mock_faiss, mock_embeddings, mock_get_api_key, mock_chunks):
        # Set up mocks
        mock_get_api_key.return_value = 'mock-api-key'
        mock_embeddings_instance = MagicMock()
        mock_embeddings.return_value = mock_embeddings_instance
        mock_faiss.from_documents.return_value = MagicMock()
        mock_chunks.return_value = ['chunk1', 'chunk2']
        
        # Test data
        processed_documents = [
            {
                'document_id': 'doc1',
                'text_content': 'Test content'
            }
        ]
        
        # Call function
        result = app.ingest_documents(processed_documents)
        
        # Check result
        self.assertTrue(result['success'])
        self.assertEqual(result['chunks_count'], 2)
        
        # Verify FAISS.from_documents was called
        mock_faiss.from_documents.assert_called_once_with(['chunk1', 'chunk2'], mock_embeddings_instance)
        
        # Verify vector store was saved
        mock_save.assert_called_once()
    
    def test_handler_ingest_documents(self):
        # Mock ingest_documents function
        app.ingest_documents = MagicMock(return_value={
            'success': True,
            'chunks_count': 5,
            'vector_store_path': 'default_vector_store'
        })
        
        # Test event
        event = {
            'operation': 'ingest_documents',
            'processed_documents': {
                'processed_documents': [
                    {'document_id': 'doc1', 'text_content': 'Test content'}
                ]
            }
        }
        
        # Call handler
        result = app.handler(event, {})
        
        # Check result
        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(result['body']['success'], True)
        
        # Verify ingest_documents was called
        app.ingest_documents.assert_called_once()


if __name__ == '__main__':
    unittest.main()