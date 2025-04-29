# Testing Commands for Banking Proposal Generator

This document provides example curl commands to test the various endpoints of the Banking Proposal Generator API once it's deployed.

## Prerequisites

- The application must be deployed to AWS
- You need the API Gateway URL (replace `https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod` with your actual URL)
- For document uploads, you'll need to base64-encode your files

## 1. Upload Document Template

```bash
curl -X POST \
  https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod/documents \
  -H 'Content-Type: application/json' \
  -d '{
    "file_name": "sample_template.docx",
    "document_type": "docx",
    "file_content_base64": "UEsDBBQABgAIAAAAIQDfpN..." 
  }'
```

## 2. Start Document Ingestion Workflow

```bash
curl -X POST \
  https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod/workflow \
  -H 'Content-Type: application/json' \
  -d '{
    "workflow_type": "document_ingestion",
    "documents": [
      {
        "document_type": "pdf",
        "s3_key": "templates/risk_disclaimers.pdf",
        "document_name": "Risk Disclaimers"
      },
      {
        "document_type": "docx",
        "s3_key": "templates/proposal_template.docx",
        "document_name": "Standard Proposal Template"
      }
    ]
  }'
```

## 3. Start Fine-Tuning Workflow

```bash
curl -X POST \
  https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod/workflow \
  -H 'Content-Type: application/json' \
  -d '{
    "workflow_type": "fine_tuning",
    "historic_proposals_key": "templates/historic_proposals.json",
    "model_name": "gpt-4-turbo"
  }'
```

## 4. Generate Proposal

```bash
curl -X POST \
  https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod/workflow \
  -H 'Content-Type: application/json' \
  -d '{
    "workflow_type": "proposal_generation",
    "client_details": {
      "client_id": "C12345",
      "client_name": "John Smith",
      "client_type": "individual",
      "risk_profile": "moderate",
      "investment_horizon": "10",
      "total_assets": 1500000.00
    },
    "financial_data_key": "templates/john_smith_financial_data.xlsx",
    "required_columns": ["asset_class", "current_value", "target_allocation"],
    "critical_columns": ["asset_class", "current_value"],
    "amount_columns": ["current_value", "target_value"],
    "allocation_column": "target_allocation"
  }'
```

## 5. Check Workflow Status

```bash
curl -X GET \
  'https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod/status?execution_arn=arn:aws:states:us-east-1:123456789012:execution:BankingProposalStateMachine:proposal-generation-abcdef123456'
```

## 6. Base64 Encode a File for Upload

You can use this command to base64 encode a file for inclusion in the curl request:

### On Linux/Mac:
```bash
base64 -i your_file.docx
```

### On Windows (PowerShell):
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("your_file.docx"))
```

## Testing with Sample Data

For initial testing, you can use the following sample files (upload these first):

1. **sample_template.docx** - A basic proposal template
2. **risk_disclaimers.pdf** - Standard risk disclaimers
3. **client_portfolio.xlsx** - Sample client portfolio data
4. **historic_proposals.json** - Sample historic proposals for fine-tuning

## Environment Setup Script

You can use this script to quickly set up a test environment with sample files:

```bash
#!/bin/bash

# Set your API Gateway URL
API_URL="https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod"

# Upload sample files
echo "Uploading sample template..."
curl -X POST "$API_URL/documents" \
  -H "Content-Type: application/json" \
  -d @sample_template_payload.json

echo "Uploading risk disclaimers..."
curl -X POST "$API_URL/documents" \
  -H "Content-Type: application/json" \
  -d @risk_disclaimers_payload.json

echo "Uploading financial data..."
curl -X POST "$API_URL/documents" \
  -H "Content-Type: application/json" \
  -d @financial_data_payload.json

echo "Uploading historic proposals..."
curl -X POST "$API_URL/documents" \
  -H "Content-Type: application/json" \
  -d @historic_proposals_payload.json

echo "Setup complete. Now you can test the workflows."
```