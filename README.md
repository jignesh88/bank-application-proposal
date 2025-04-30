# Banking Proposal Generator

An AI-driven banking and wealth management proposal generator that leverages AWS Lambda, Step Functions, and GPT-4-Turbo to automate the creation of personalized financial advice documents.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![AWS](https://img.shields.io/badge/AWS-Serverless-orange.svg)
![OpenAI](https://img.shields.io/badge/AI-GPT--4--Turbo-green.svg)

## 🚀 Key Features

- **Document Processing**: Automatically extracts text and structure from document templates, clause libraries, and financial data using AWS Textract
- **Retrieval-Augmented Generation (RAG)**: Ingests documents into a vector store for context-aware proposal generation
- **Fine-Tuned LLM**: Uses GPT-4-Turbo fine-tuned on historic proposals to ensure accuracy
- **Schema Validation**: Implements strong guardrails with Pydantic schema validation
- **Serverless Architecture**: Built with AWS Lambda and Step Functions for scalability

## 💡 Benefits

- **Drastically Reduced Drafting Time**: Cut proposal creation time from ~3 hours to 15 minutes
- **High Accuracy**: Achieves ≥90% template-field accuracy through fine-tuning
- **Regulatory Compliance**: Guarantees all legally-required sections are present
- **Financial Consistency**: Ensures numbers reconcile with attached spreadsheets
- **Cost Efficiency**: Serverless architecture provides pay-per-use pricing

## 🏗️ Architecture

The system is built on AWS serverless technologies:

![Architecture Diagram](docs/system-architecture.md)

### Components:

- **AWS Lambda**: Handles individual processing steps
- **AWS Step Functions**: Orchestrates the entire workflow
- **AWS S3**: Stores templates, proposals, and vector data
- **AWS Textract**: Extracts text from documents
- **AWS Comprehend**: Recognizes entities in financial documents
- **AWS API Gateway**: Provides HTTP endpoints
- **AWS Parameter Store**: Securely manages API keys

### Workflow Diagram:

![Sequence Diagram](docs/sequence-diagram.md)

## 🧩 Quick Start Guide

### Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 14.x or later (for CDK)
- Python 3.9 or later
- OpenAI API Key

### 1. Clone the Repository

```bash
git clone https://github.com/jignesh88/bank-application-proposal.git
cd bank-application-proposal
```

### 2. Store OpenAI API Key in AWS Parameter Store

```bash
aws ssm put-parameter \
    --name "/banking-proposal/openai-api-key" \
    --value "your-openai-api-key" \
    --type SecureString
```

### 3. Deploy the Infrastructure

```bash
cd infrastructure
npm install
npm run build
cdk bootstrap  # Only needed first time
cdk deploy
```

Note the API Gateway URL in the outputs.

### 4. Test the Application

Upload a sample document template:

```bash
curl -X POST \
  https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod/documents \
  -H 'Content-Type: application/json' \
  -d '{
    "file_name": "sample_template.docx",
    "document_type": "docx",
    "file_content_base64": "'$(base64 -w 0 sample_template.docx)'" 
  }'
```

See the [testing commands documentation](docs/testing-commands.md) for more examples.

### 5. Clean Up When Done

To avoid ongoing AWS charges when you're finished testing:

```bash
cd infrastructure
cdk destroy
```

For complete cleanup of retained resources (S3 buckets and DynamoDB):

```bash
# Get bucket names (if you didn't note them during deployment)
aws s3 ls | grep bankingproposal

# Empty each bucket
aws s3 rm s3://BUCKET_NAME --recursive

# Delete each bucket
aws s3 rb s3://BUCKET_NAME

# Delete DynamoDB table (get the name from AWS Console if needed)
aws dynamodb delete-table --table-name TABLE_NAME
```

## 📝 Detailed Usage

After deployment, use the API Gateway endpoints to interact with the system:

### Document Ingestion

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
      }
    ]
  }'
```

### Proposal Generation

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
    "financial_data_key": "templates/john_smith_financial_data.xlsx"
  }'
```

See the [testing commands documentation](docs/testing-commands.md) for more examples.

## 📋 Project Structure

```
├── infrastructure/          # AWS CDK infrastructure code
├── lambdas/                 # Lambda function implementations
│   ├── api_handler/         # API Gateway handler
│   ├── document_processor/  # Document processing functions
│   ├── fine_tuning/         # LLM fine-tuning functions
│   ├── proposal_generator/  # Proposal generation functions
│   └── rag_pipeline/        # RAG system functions
├── stepfunctions/           # Step Functions workflow definition
├── layers/                  # Lambda layers with dependencies
├── docs/                    # Documentation and diagrams
└── tests/                   # Unit and integration tests
```

## 🖼️ Architecture Diagrams

- [Component Diagram](docs/component-diagram.md)
- [Sequence Diagram](docs/sequence-diagram.md)
- [System Architecture](docs/system-architecture.md)
- [Data Flow Diagram](docs/data-flow-diagram.md)

## 🧪 Testing

Run unit tests with:

```bash
python -m unittest discover tests
```

Test the infrastructure code with:

```bash
cd infrastructure
npm test
```

Test deployed endpoints using curl commands in [testing-commands.md](docs/testing-commands.md).

## 🚨 Error Handling

The system includes robust error handling:

- **Schema Validation**: Catches malformed data early
- **Regeneration**: Automatically attempts to fix invalid proposals
- **Fallback Generation**: Uses template-based fallback when AI generation fails
- **Step Functions Error Handling**: Includes retry and catch mechanisms for all workflow steps

## 🛡️ Security Considerations

- All API keys are stored in AWS Parameter Store
- S3 buckets are configured with appropriate access controls
- IAM roles follow least privilege principle
- Input validation prevents injection attacks
- Client data is encrypted in transit and at rest

## 📈 Cost Management

To manage AWS costs effectively:

1. **During Development**: Destroy infrastructure when not in use
2. **In Production**: Monitor usage with CloudWatch and AWS Cost Explorer
3. **Lambda Optimization**: Adjust memory allocation for best performance/cost ratio
4. **S3 Lifecycle Policies**: Automatically transition older data to cheaper storage classes

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🔮 Future Enhancements

- Integration with CRM systems for client data
- Additional document format outputs (PDF, HTML)
- Interactive proposal editing interface
- Multi-language support
- Enhanced compliance checks for different regulatory jurisdictions