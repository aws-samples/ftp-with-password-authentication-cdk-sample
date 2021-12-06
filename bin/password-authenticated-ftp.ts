#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { PasswordAuthenticatedFtpStack } from '../lib/password-authenticated-ftp-stack';

const app = new cdk.App();
new PasswordAuthenticatedFtpStack(app, "FtpSampleStack");
