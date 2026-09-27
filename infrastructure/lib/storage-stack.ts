import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export class JevnoidStorageStack extends cdk.Stack {
  public readonly vitalsTable: dynamodb.Table;
  public readonly knowledgeBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // DynamoDB: Organism Vitals & State (100% Permanent Free Tier: 1 RCU / 1 WCU).
    // The soup field is packed to base64 (src/domain/tierra_vm.py) specifically so a heartbeat's
    // burst of colony writes fits DynamoDB's burst-capacity allowance at the lowest provisioned tier.
    this.vitalsTable = new dynamodb.Table(this, 'JevnoidVitalsTable', {
      tableName: 'JevnoidVitals',
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PROVISIONED,
      readCapacity: 1,
      writeCapacity: 1,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // Sandbox friendly
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: false },
    });

    // S3: Knowledge Crystals & Archived Foraged Content (Free-tier safe)
    this.knowledgeBucket = new s3.Bucket(this, 'JevnoidKnowledgeBucket', {
      bucketName: `jevnoid-knowledge-${cdk.Aws.ACCOUNT_ID}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [
        {
          id: 'ExpireRawPreyAfter30Days',
          expiration: cdk.Duration.days(30),
          prefix: 'raw/',
        },
      ],
    });

    new cdk.CfnOutput(this, 'VitalsTableName', {
      value: this.vitalsTable.tableName,
      description: 'DynamoDB Table name for Jevnoid vitals',
    });

    new cdk.CfnOutput(this, 'KnowledgeBucketName', {
      value: this.knowledgeBucket.bucketName,
      description: 'S3 Bucket name for knowledge crystals',
    });
  }
}
