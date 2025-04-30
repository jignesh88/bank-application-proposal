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

### Steps to Deploy

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

5. Take note of the outputs, which include:
   - API Gateway URL
   - S3 bucket names
   - Step Functions state machine ARN

### Destroying the Infrastructure

After testing is complete, you can destroy all resources to avoid incurring AWS charges:

```
cdk destroy
```

When prompted, confirm that you want to delete the stack. This will remove all resources except:

- S3 buckets with the `RemovalPolicy.RETAIN` setting (to prevent accidental data loss)
- DynamoDB tables with the `RemovalPolicy.RETAIN` setting

To completely remove retained resources after confirming you no longer need the data:

1. Empty the S3 buckets using the AWS Console or CLI:
   ```
   aws s3 rm s3://BUCKET_NAME --recursive
   ```

2. Delete the buckets manually:
   ```
   aws s3 rb s3://BUCKET_NAME
   ```

3. Delete the DynamoDB table:
   ```
   aws dynamodb delete-table --table-name TABLE_NAME
   ```

## Configuration

The stack uses the following configuration sources:

- Environment variables
- AWS Parameter Store for secrets
- CDK context values from cdk.json

### Required Parameters

Before deployment, ensure the following parameter exists in AWS Parameter Store:

- `/banking-proposal/openai-api-key`: Your OpenAI API key (as a SecureString)

You can create this parameter using the AWS CLI:

```
aws ssm put-parameter \
    --name "/banking-proposal/openai-api-key" \
    --value "your-openai-api-key" \
    --type SecureString
```

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

## Monitoring and Maintenance

After deployment, you can monitor the application through:

- AWS CloudWatch Logs for Lambda functions
- Step Functions execution history
- CloudWatch metrics for API Gateway

## Costs

This serverless infrastructure primarily incurs costs when used. Key cost factors include:

- Lambda invocations and execution duration
- API Gateway requests
- S3 storage and requests
- Step Functions state transitions
- OpenAI API usage (external to AWS)

When not in use, storage costs for S3 and DynamoDB will be the main ongoing expenses.