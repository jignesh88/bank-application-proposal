import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as stepfunctions from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export class BankingProposalStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Storage resources
    const templatesBucket = new s3.Bucket(this, 'TemplatesBucket', {
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [
        {
          expiration: cdk.Duration.days(365),
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(90),
            }
          ]
        }
      ]
    });

    const proposalsBucket = new s3.Bucket(this, 'ProposalsBucket', {
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [
        {
          expiration: cdk.Duration.days(365),
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(90),
            }
          ]
        }
      ]
    });

    const vectorStoreBucket = new s3.Bucket(this, 'VectorStoreBucket', {
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // DynamoDB Table for fine-tuning jobs tracking
    const fineTuningTable = new dynamodb.Table(this, 'FineTuningTable', {
      partitionKey: { name: 'job_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecovery: true,
      timeToLiveAttribute: 'ttl'
    });

    // Parameter Store for secrets
    const openaiApiKey = ssm.StringParameter.fromSecureStringParameterAttributes(this, 'OpenAIApiKey', {
      parameterName: '/banking-proposal/openai-api-key',
      version: 1,
    });

    // Lambda Layer for common dependencies
    const commonLayer = new lambda.LayerVersion(this, 'CommonDependencies', {
      code: lambda.Code.fromAsset('../layers/common'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_9],
      description: 'Common dependencies for banking proposal lambdas',
    });

    // IAM role for Lambda functions
    const lambdaRole = new iam.Role(this, 'BankingProposalLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant permissions to the Lambda role
    templatesBucket.grantReadWrite(lambdaRole);
    proposalsBucket.grantReadWrite(lambdaRole);
    vectorStoreBucket.grantReadWrite(lambdaRole);
    openaiApiKey.grantRead(lambdaRole);
    fineTuningTable.grantReadWriteData(lambdaRole);

    // Allow Lambda to use Textract and Comprehend
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'textract:*',
        'comprehend:*',
      ],
      resources: ['*'],
    }));

    // Lambda functions
    const documentProcessorLambda = new lambda.Function(this, 'DocumentProcessorLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset('../lambdas/document_processor'),
      handler: 'app.handler',
      timeout: cdk.Duration.minutes(15),
      memorySize: 1024,
      environment: {
        TEMPLATES_BUCKET: templatesBucket.bucketName,
        PROPOSALS_BUCKET: proposalsBucket.bucketName,
        OPENAI_API_KEY_PARAM: openaiApiKey.parameterName,
      },
      layers: [commonLayer],
      role: lambdaRole,
    });

    const ragLambda = new lambda.Function(this, 'RAGLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset('../lambdas/rag_pipeline'),
      handler: 'app.handler',
      timeout: cdk.Duration.minutes(15),
      memorySize: 2048,
      environment: {
        TEMPLATES_BUCKET: templatesBucket.bucketName,
        VECTOR_STORE_BUCKET: vectorStoreBucket.bucketName,
        OPENAI_API_KEY_PARAM: openaiApiKey.parameterName,
      },
      layers: [commonLayer],
      role: lambdaRole,
    });

    const fineTuningLambda = new lambda.Function(this, 'FineTuningLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset('../lambdas/fine_tuning'),
      handler: 'app.handler',
      timeout: cdk.Duration.minutes(15),
      memorySize: 1024,
      environment: {
        TEMPLATES_BUCKET: templatesBucket.bucketName,
        OPENAI_API_KEY_PARAM: openaiApiKey.parameterName,
        FINE_TUNING_TABLE: fineTuningTable.tableName,
      },
      layers: [commonLayer],
      role: lambdaRole,
    });

    const proposalGeneratorLambda = new lambda.Function(this, 'ProposalGeneratorLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset('../lambdas/proposal_generator'),
      handler: 'app.handler',
      timeout: cdk.Duration.minutes(15),
      memorySize: 2048,
      environment: {
        PROPOSALS_BUCKET: proposalsBucket.bucketName,
        VECTOR_STORE_BUCKET: vectorStoreBucket.bucketName,
        OPENAI_API_KEY_PARAM: openaiApiKey.parameterName,
        FINE_TUNED_MODEL: 'gpt-4-turbo',  // Update this when you have a fine-tuned model
      },
      layers: [commonLayer],
      role: lambdaRole,
    });

    // Get the Step Functions workflow definition from JSON file
    const workflowDefinitionJson = require('../../stepfunctions/workflow.json');
    
    // Replace the Lambda ARNs in the workflow definition
    const workflowDefinition = JSON.stringify(workflowDefinitionJson)
      .replace('${DocumentProcessorLambdaArn}', documentProcessorLambda.functionArn)
      .replace('${RAGLambdaArn}', ragLambda.functionArn)
      .replace('${FineTuningLambdaArn}', fineTuningLambda.functionArn)
      .replace('${ProposalGeneratorLambdaArn}', proposalGeneratorLambda.functionArn);
    
    // Create the state machine
    const stateMachine = new stepfunctions.StateMachine(this, 'BankingProposalStateMachine', {
      definitionBody: stepfunctions.DefinitionBody.fromString(workflowDefinition),
      timeout: cdk.Duration.minutes(30),
      logs: {
        destination: new logs.LogGroup(this, 'StateMachineLogGroup', {
          retention: logs.RetentionDays.ONE_MONTH
        }),
        includeExecutionData: true,
        level: stepfunctions.LogLevel.ALL
      },
      tracingEnabled: true,
    });

    // API Gateway
    const api = new apigateway.RestApi(this, 'BankingProposalApi', {
      description: 'Banking Proposal Generator API',
      deployOptions: {
        stageName: 'prod',
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
      },
    });

    // Create API Gateway Lambda to start workflow
    const apiHandlerLambda = new lambda.Function(this, 'ApiHandlerLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset('../lambdas/api_handler'),
      handler: 'app.handler',
      environment: {
        STATE_MACHINE_ARN: stateMachine.stateMachineArn,
        TEMPLATES_BUCKET: templatesBucket.bucketName,
      },
      layers: [commonLayer],
      role: lambdaRole,
    });
    
    // Grant permission to start execution
    stateMachine.grantStartExecution(apiHandlerLambda);
    
    // Add resources and methods to API Gateway
    const workflowResource = api.root.addResource('workflow');
    workflowResource.addMethod('POST', new apigateway.LambdaIntegration(apiHandlerLambda));
    
    // Add status check endpoint
    const statusResource = api.root.addResource('status');
    statusResource.addMethod('GET', new apigateway.LambdaIntegration(apiHandlerLambda));
    
    // Add document upload resource
    const documentsResource = api.root.addResource('documents');
    documentsResource.addMethod('POST', new apigateway.LambdaIntegration(apiHandlerLambda));
    
    // Outputs
    new cdk.CfnOutput(this, 'TemplatesBucketName', {
      value: templatesBucket.bucketName,
      description: 'S3 bucket for document templates',
    });
    
    new cdk.CfnOutput(this, 'ProposalsBucketName', {
      value: proposalsBucket.bucketName,
      description: 'S3 bucket for generated proposals',
    });
    
    new cdk.CfnOutput(this, 'VectorStoreBucketName', {
      value: vectorStoreBucket.bucketName,
      description: 'S3 bucket for vector store data',
    });
    
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url,
      description: 'URL of the API Gateway endpoint',
    });
    
    new cdk.CfnOutput(this, 'StateMachineArn', {
      value: stateMachine.stateMachineArn,
      description: 'ARN of the Step Functions state machine',
    });
  }
}
