#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { BankingProposalStack } from '../lib/banking-proposal-stack';

const app = new cdk.App();

new BankingProposalStack(app, 'BankingProposalStack', {
  env: { 
    account: process.env.CDK_DEFAULT_ACCOUNT, 
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1' 
  },
  description: 'Banking Proposal Generator serverless application using Lambda, Step Functions, and OpenAI',
  tags: {
    Project: 'BankingProposal',
    Environment: 'Production',
    Application: 'ProposalGenerator'
  }
});
