import unittest
import json
import os
import sys
import boto3
import tempfile
from unittest.mock import patch, MagicMock

# Add the lambda function directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'document_processor'))
import app

class TestDocumentProcessor(unittest.TestCase):
    """Test cases for the Document Processor Lambda"""
    
    @patch('app.s3')
    @patch('app.textract')
    def test_extract_text_with_textract(self, mock_textract, mock_s3):
        # Mock the Textract response
        mock_textract.detect_document_text.return_value = {
            'Blocks': [
                {'BlockType': 'LINE', 'Text': 'This is a test line 1'},
                {'BlockType': 'WORD', 'Text': 'Ignored word'},
                {'BlockType': 'LINE', 'Text': 'This is a test line 2'}
            ]
        }
        
        # Call the function
        result = app.extract_text_with_textract('test-bucket', 'test-document.pdf')
        
        # Check the result
        expected_text = "This is a test line 1\nThis is a test line 2\n"
        self.assertEqual(result, expected_text)
        
        # Verify Textract was called correctly
        mock_textract.detect_document_text.assert_called_once_with(
            Document={
                'S3Object': {
                    'Bucket': 'test-bucket',
                    'Name': 'test-document.pdf'
                }
            }
        )
    
    @patch('app.s3')
    @patch('app.textract')
    def test_process_document_pdf(self, mock_textract, mock_s3):
        # Mock the Textract response
        mock_textract.detect_document_text.return_value = {
            'Blocks': [
                {'BlockType': 'LINE', 'Text': 'Sample document content'}
            ]
        }
        
        # Test data
        document_data = {
            'document_type': 'pdf',
            's3_key': 'templates/test.pdf',
            'document_name': 'test'
        }
        
        # Call the function
        result = app.process_document(document_data)
        
        # Check the result has the expected fields
        self.assertEqual(result['document_id'], 'test')
        self.assertEqual(result['document_type'], 'pdf')
        self.assertEqual(result['s3_key'], 'templates/test.pdf')
        self.assertEqual(result['text_content'], 'Sample document content\n')
        self.assertIn('processed_timestamp', result)
        
    @patch('app.s3')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pandas.read_excel')
    def test_process_document_excel(self, mock_pd_read_excel, mock_temp_file, mock_s3):
        # Mock the pandas DataFrame
        mock_df = MagicMock()
        mock_df.columns.tolist.return_value = ['Column1', 'Column2']
        mock_df.__len__.return_value = 10
        mock_df.isnull().any().any.return_value = False
        mock_pd_read_excel.return_value = mock_df
        
        # Mock the temp file
        mock_temp_file_instance = MagicMock()
        mock_temp_file_instance.__enter__.return_value = mock_temp_file_instance
        mock_temp_file_instance.name = '/tmp/test.xlsx'
        mock_temp_file.return_value = mock_temp_file_instance
        
        # Test data
        document_data = {
            'document_type': 'xlsx',
            's3_key': 'templates/test.xlsx',
            'document_name': 'test'
        }
        
        # Call the function
        result = app.process_document(document_data)
        
        # Check the result has the expected fields
        self.assertEqual(result['document_id'], 'test')
        self.assertEqual(result['document_type'], 'xlsx')
        self.assertEqual(result['s3_key'], 'templates/test.xlsx')
        self.assertEqual(result['column_names'], ['Column1', 'Column2'])
        self.assertEqual(result['row_count'], 10)
        self.assertEqual(result['has_missing_values'], False)
        self.assertIn('processed_timestamp', result)
        
        # Verify download was called correctly
        mock_s3.download_file.assert_called_once_with(
            app.TEMPLATES_BUCKET, 'templates/test.xlsx', '/tmp/test.xlsx')
    
    def test_lambda_handler_process_documents(self):
        # Mock the process_document function
        app.process_document = MagicMock(return_value={
            'document_id': 'test',
            'text_content': 'Sample content'
        })
        
        # Test event
        event = {
            'operation': 'process_documents',
            'documents': [
                {'document_type': 'pdf', 's3_key': 'test1.pdf'},
                {'document_type': 'docx', 's3_key': 'test2.docx'}
            ]
        }
        
        # Call the handler
        result = app.handler(event, {})
        
        # Check the result
        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(len(result['processed_documents']), 2)
        self.assertEqual(app.process_document.call_count, 2)


if __name__ == '__main__':
    unittest.main()