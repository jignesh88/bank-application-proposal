import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { BankingProposalStack } from '../lib/banking-proposal-stack';

describe('BankingProposalStack', () => {
  let template: Template;
  
  beforeAll(() => {
    const app = new cdk.App();
    const stack = new BankingProposalStack(app, 'TestStack');
    template = Template.fromStack(stack);
  });

  test('S3 Buckets Created', () => {
    template.resourceCountIs('AWS::S3::Bucket', 3); // Templates, Proposals, VectorStore
  });

  test('Lambda Functions Created', () => {
    template.resourceCountIs('AWS::Lambda::Function', 5); // 4 service lambdas + API handler
    
    // Check Document Processor Lambda
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'app.handler',
      Runtime: 'python3.9',
      Timeout: 900, // 15 minutes
      MemorySize: 1024,
      Environment: {
        Variables: {
          TEMPLATES_BUCKET: {
            Ref: expect.stringMatching(/TemplatesBucket/)
          }
        }
      }
    });
  });

  test('Step Functions Created', () => {
    template.resourceCountIs('AWS::StepFunctions::StateMachine', 1);
  });

  test('API Gateway Created', () => {
    template.resourceCountIs('AWS::ApiGateway::RestApi', 1);
    template.resourceCountIs('AWS::ApiGateway::Method', 3); // workflow, status, documents
  });

  test('DynamoDB Table Created', () => {
    template.resourceCountIs('AWS::DynamoDB::Table', 1);
    
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      KeySchema: [
        {
          AttributeName: 'job_id',
          KeyType: 'HASH'
        }
      ],
      BillingMode: 'PAY_PER_REQUEST',
      PointInTimeRecoverySpecification: {
        PointInTimeRecoveryEnabled: true
      }
    });
  });

  test('IAM Roles Created with Correct Permissions', () => {
    template.hasResourceProperties('AWS::IAM::Role', {
      ManagedPolicyArns: [
        {
          'Fn::Join': [
            '',
            [
              'arn:',
              { Ref: 'AWS::Partition' },
              ':iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
            ]
          ]
        }
      ],
      AssumeRolePolicyDocument: {
        Statement: [
          {
            Action: 'sts:AssumeRole',
            Effect: 'Allow',
            Principal: {
              Service: 'lambda.amazonaws.com'
            }
          }
        ]
      }
    });
    
    // Check policy for Textract and Comprehend access
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: [
          {
            Action: [
              'textract:*',
              'comprehend:*'
            ],
            Effect: 'Allow',
            Resource: '*'
          }
        ]
      }
    });
  });
});
