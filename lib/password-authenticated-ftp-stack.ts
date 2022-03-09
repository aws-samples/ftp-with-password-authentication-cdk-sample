import * as cdk from "aws-cdk-lib/core";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";
import { PasswordAuthenticatedFtp } from "./ftp/password-authenticated-ftp";
import { FtpUser } from "./ftp/ftp-user";

export class PasswordAuthenticatedFtpStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const vpc = new ec2.Vpc(this, "Vpc", {
      natGateways: 1,
    });

    // an AWS Transfer server
    const ftp = new PasswordAuthenticatedFtp(this, `Ftp`, {
      vpc,
      protocol: "SFTP",
    });

    // an S3 bucket which is a destination for FTP transfers
    const bucket = new s3.Bucket(this, `Bucket`, {
      encryption: s3.BucketEncryption.S3_MANAGED,
      autoDeleteObjects: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create an FTP user with randomly generated password
    new FtpUser(this, `User1`, {
      transferServerId: ftp.server.attrServerId,
      accessibleBucket: bucket,
      homeDirectory: "home",
    });

    // You can specify password explicitly
    new FtpUser(this, `User2`, {
      transferServerId: ftp.server.attrServerId,
      accessibleBucket: bucket,
      homeDirectory: "home",
      password: "password",
    });

    // an EC2 instance to test FTP connection
    const client = new ec2.Instance(this, `Client`, {
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
      machineImage: new ec2.AmazonLinuxImage({
        generation: ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
      }),
      vpc,
      blockDevices: [
        {
          deviceName: "/dev/xvda",
          volume: ec2.BlockDeviceVolume.ebs(30, { encrypted: true }),
        },
      ],
    });

    // Policy for SSM access to the EC2 instance
    client.role.addManagedPolicy(iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonSSMManagedInstanceCore"));

    new cdk.CfnOutput(this, "FtpClientInstanceName", { value: client.instanceId });
    new cdk.CfnOutput(this, "DestinationS3BucketName", { value: bucket.bucketName });
  }
}
