import * as cdk from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";
import { PasswordAuthenticatedFtpStack } from "../lib/password-authenticated-ftp-stack";

test("Snapshot test", () => {
  const app = new cdk.App();
  const stack = new PasswordAuthenticatedFtpStack(app, "MyTestStack");
  const template = Template.fromStack(stack);
  expect(template).toMatchSnapshot();
});
