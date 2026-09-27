import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';

// SecureString parameters are created out-of-band (see docs/runbook.md) so secret values
// never appear in CloudFormation templates or CDK assets.
export const TYPESAFE_API_KEY_PARAM = '/jevnoid/typesafe-api-key';
export const CF_API_TOKEN_PARAM = '/jevnoid/cloudflare-kv-api-token';

export interface ComputeStackProps extends cdk.StackProps {
  vitalsTable: dynamodb.Table;
  knowledgeBucket: s3.Bucket;
  cloudflareAccountId: string;
  cloudflareKvNamespaceId: string;
}

export class JevnoidComputeStack extends cdk.Stack {
  public readonly pulseFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    // Lambda Layer for Python Dependencies (typesafe_sdk, httpx, pydantic)
    const dependenciesLayer = new lambda.LayerVersion(this, 'JevnoidDependenciesLayer', {
      layerVersionName: 'JevnoidDependenciesLayer',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda_layer')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      compatibleArchitectures: [lambda.Architecture.X86_64],
      description: 'Runtime dependencies for Jevnoid: typesafe_sdk, httpx, pydantic',
    });

    // Lambda: Heartbeat Life Engine (Free tier safe: 256MB memory, 15s timeout, x86_64)
    this.pulseFunction = new lambda.Function(this, 'JevnoidPulseFunction', {
      functionName: 'JevnoidHeartbeatFunction',
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.X86_64,
      handler: 'index.handler',
      // Allowlist: ship only the Python app so local secrets or artifacts can never leak into the bundle.
      code: lambda.Code.fromAsset(path.join(__dirname, '../../'), {
        ignoreMode: cdk.IgnoreMode.GIT,
        exclude: ['*', '!/index.py', '!/src/', '!/src/**', '**/__pycache__', '**/*.pyc', '.DS_Store'],
      }),
      layers: [dependenciesLayer],
      memorySize: 256,
      // Every organism forages concurrently each heartbeat; 60s leaves headroom for slow pages and Jev.
      timeout: cdk.Duration.seconds(60),
      environment: {
        VITALS_TABLE: props.vitalsTable.tableName,
        KNOWLEDGE_BUCKET: props.knowledgeBucket.bucketName,
        POWERTOOLS_SERVICE_NAME: 'jevnoid-life',
        TYPESAFE_API_KEY_PARAM: TYPESAFE_API_KEY_PARAM,
        CF_API_TOKEN_PARAM: CF_API_TOKEN_PARAM,
        CF_ACCOUNT_ID: props.cloudflareAccountId,
        CF_KV_NAMESPACE_ID: props.cloudflareKvNamespaceId,
      },
    });

    this.pulseFunction.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ssm:GetParameter'],
      resources: [TYPESAFE_API_KEY_PARAM, CF_API_TOKEN_PARAM].map(name =>
        cdk.Arn.format({ service: 'ssm', resource: 'parameter', resourceName: name.replace(/^\//, '') }, this)),
    }));

    // Grant minimum required permissions
    props.vitalsTable.grantReadWriteData(this.pulseFunction);
    props.knowledgeBucket.grantReadWrite(this.pulseFunction);

    // EventBridge: Periodic Heartbeat Pulse. A slow, deliberate cadence: growth, upkeep, and hazard
    // rolls all happen once per pulse, so this interval sets the ecosystem's overall pace of change.
    const heartbeatRule = new events.Rule(this, 'JevnoidHeartbeatRule', {
      ruleName: 'JevnoidPeriodicHeartbeat',
      description: 'Periodic pulse trigger for Jevnoid autonomous digital organisms',
      schedule: events.Schedule.rate(cdk.Duration.hours(3)),
    });

    heartbeatRule.addTarget(new targets.LambdaFunction(this.pulseFunction));

    new cdk.CfnOutput(this, 'PulseFunctionArn', {
      value: this.pulseFunction.functionArn,
      description: 'ARN of the Jevnoid Life Pulse Lambda Function',
    });
  }
}
