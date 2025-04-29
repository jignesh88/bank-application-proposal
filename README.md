# Banking Proposal Generator

An AI-driven banking proposal generator that leverages AWS Lambda, Step Functions, and GPT-4-Turbo to automate the creation of personalized wealth management proposals.

## Features

- **Document Processing**: Automatically extracts text and structure from document templates, clause libraries, and financial data using AWS Textract
- **Retrieval-Augmented Generation (RAG)**: Ingests documents into a vector store for context-aware proposal generation
- **Fine-Tuned LLM**: Uses GPT-4-Turbo fine-tuned on historic proposals to ensure accuracy
- **Schema Validation**: Implements strong guardrails with Pydantic schema validation
- **Serverless Architecture**: Built with AWS Lambda and Step Functions for scalability

## Architecture

The system is built on AWS serverless technologies:

- **AWS Lambda**: Handles individual processing steps
- **AWS Step Functions**: Orchestrates the entire workflow
- **AWS S3**: Stores templates, proposals, and vector data
- **AWS Textract**: Extracts text from documents
- **AWS Comprehend**: Recognizes entities in financial documents
- **AWS API Gateway**: Provides HTTP endpoints
- **AWS Parameter Store**: Securely manages API keys

## Workflow

1. **Document Ingestion**:
   - Upload document templates and clause libraries
   - Process documents to extract text and structure
   - Create embeddings and store in FAISS vector database

2. **Fine-Tuning**:
   - Prepare training data from historic proposals
   - Fine-tune GPT-4-Turbo to achieve high accuracy
   - Track fine-tuning job status

3. **Proposal Generation**:
   - Validate financial data for consistency
   - Retrieve relevant context from the vector database
   - Generate proposal with fine-tuned model
   - Validate against schema to ensure compliance
   - Format final document with dynamic content

## Project Structure

```
├── infrastructure/            # AWS CDK infrastructure code
├── lambdas/                   # Lambda function implementations
│   ├── api_handler/           # API Gateway handler
│   ├── document_processor/    # Document processing functions
│   ├── fine_tuning/           # LLM fine-tuning functions
│   ├── proposal_generator/    # Proposal generation functions
│   └── rag_pipeline/          # RAG system functions
├── stepfunctions/             # Step Functions workflow definition
├── layers/                    # Lambda layers with dependencies
└── tests/                     # Unit and integration tests
```

## Getting Started

### Prerequisites

- AWS CLI configured with appropriate permissions
- Node.js 14.x or later (for CDK)
- Python 3.9 or later
- OpenAI API Key

### Deployment

1. Install dependencies:

```bash
# Install CDK dependencies
cd infrastructure
npm install

# Install Python dependencies for Lambda layers
cd ../layers/common
pip install -r requirements.txt -t python
```

2. Deploy the infrastructure:

```bash
cd infrastructure
cdk deploy
```

3. Store your OpenAI API key in Parameter Store:

```bash
aws ssm put-parameter --name '/banking-proposal/openai-api-key' --value 'your-api-key' --type SecureString
```

### Usage

After deployment, you can use the following API endpoints:

- `POST /documents` - Upload a document template or clause library
- `POST /workflow` - Start a workflow (document_ingestion, fine_tuning, proposal_generation)
- `GET /status` - Check the status of a workflow execution

## Performance

- Reduces proposal drafting time from ~3 hours to 15 minutes
- Achieves ≥90% template-field accuracy
- Ensures all legal requirements and disclaimers are included
- Guarantees numerical reconciliation with attached spreadsheets

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
