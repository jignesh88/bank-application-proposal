# Banking Proposal Generator Infrastructure

This directory contains the AWS CDK code that defines the infrastructure for the Banking Proposal Generator application.

## Components

The infrastructure defines the following AWS resources:

- **S3 Buckets**:
  - Templates Bucket: Stores document templates and input data
  - Proposals Bucket: Stores generated proposal documents
  - Vector Store Bucket: Stores vector embeddings for the RAG system

- **Lambda Functions**:
  - Document Processor: Processes templates and financial data
  - RAG Pipeline: Handles vector retrieval and embeddings
  - Fine-Tuning: Manages OpenAI model fine-tuning
  - Proposal Generator: Creates and validates proposals
  - API Handler: Interfaces with API Gateway

- **Step Functions Workflow**: Orchestrates the entire process

- **API Gateway**: Provides HTTP endpoints for interacting with the system

- **DynamoDB**: Tracks fine-tuning job status

## Deployment Instructions

### Prerequisites

- Node.js 14.x or later
- AWS CLI configured with appropriate credentials
- AWS CDK v2 installed globally (`npm install -g aws-cdk`)

### Steps

1. Install dependencies:
   ```
   npm install
   ```

2. Build the TypeScript code:
   ```
   npm run build
   ```

3. Bootstrap AWS environment (first time only):
   ```
   cdk bootstrap
   ```

4. Deploy the stack:
   ```
   cdk deploy
   ```

## Configuration

The stack uses the following configuration sources:

- Environment variables
- AWS Parameter Store for secrets
- CDK context values from cdk.json

### Required Parameters

Before deployment, ensure the following parameter exists in AWS Parameter Store:

- `/banking-proposal/openai-api-key`: Your OpenAI API key (as a SecureString)

## Customization

To customize the deployment:

1. Modify `lib/banking-proposal-stack.ts` to add or adjust resources
2. Update Lambda environment variables as needed
3. Adjust Step Functions workflow in `stepfunctions/workflow.json`

## Security Considerations

- All S3 buckets have public access blocked
- Encryption is enabled for all data storage
- IAM permissions follow least privilege principle
- Sensitive values are stored in Parameter Store