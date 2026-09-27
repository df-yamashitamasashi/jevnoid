#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { JevnoidStorageStack } from '../lib/storage-stack';
import { JevnoidComputeStack } from '../lib/compute-stack';

const app = new cdk.App();

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'ap-northeast-1',
};

const requireContext = (key: string): string => {
  const value = app.node.tryGetContext(key);
  if (!value) throw new Error(`Missing CDK context "${key}" (pass it with: cdk deploy -c ${key}=...)`);
  return value;
};

// 1. Storage Stack (DynamoDB & S3)
const storageStack = new JevnoidStorageStack(app, 'JevnoidStorageStack', {
  env,
  description: 'Jevnoid Living Organism Storage Stack (DynamoDB, S3)',
});

// 2. Compute Stack (Lambda & EventBridge heartbeat). The public site is served by Cloudflare Pages,
//    so nothing in AWS is reachable from the internet.
const computeStack = new JevnoidComputeStack(app, 'JevnoidComputeStack', {
  env,
  vitalsTable: storageStack.vitalsTable,
  knowledgeBucket: storageStack.knowledgeBucket,
  cloudflareAccountId: requireContext('cloudflareAccountId'),
  cloudflareKvNamespaceId: requireContext('cloudflareKvNamespaceId'),
  description: 'Jevnoid Living Organism Life Engine Compute Stack (Lambda, EventBridge)',
});
computeStack.addStackDependency(storageStack);

// Tagging for cost attribution & sandbox management
cdk.Tags.of(app).add('Project', 'Jevnoid');
cdk.Tags.of(app).add('Environment', 'Sandbox');
cdk.Tags.of(app).add('ManagedBy', 'AWS-CDK-v2');

app.synth();
