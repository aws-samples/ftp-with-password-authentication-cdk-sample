import json
import boto3
import os
from moto import mock_secretsmanager

region = os.environ["AWS_REGION"]


def create_secret(client, server_id, username, password):
    role_arn = "roleArn"
    home_directory_details = json.dumps({
        "Entry": "/",
        "Target": "/bucketName/homeDirectory"
    })
    client.create_secret(
        Name=f"ftpSecret/{server_id}/{username}",
        SecretString=json.dumps({
            "Role": role_arn,
            "HomeDirectoryDetails": home_directory_details,
            "Password": password
        })
    )
    return role_arn, home_directory_details


@mock_secretsmanager
def test_with_correct_password():
    from index import handler
    client = boto3.session.Session().client(
        service_name="secretsmanager", region_name=region)
    server_id = "server"
    username = "user"
    password = "password"
    role_arn, home_directory_details = create_secret(
        client, server_id, username, password)

    event = {
        "pathParameters": {
            "serverId": server_id,
            "username": username,
        },
        "queryStringParameters": {
            "protocol": "FTP",
        },
        "requestContext": {
            "identity": {
                "sourceIp": "8.8.8.8",
            },
        },
        "headers": {
            "Password": password
        }
    }

    response = handler(event, {})
    assert response["statusCode"] == 200

    policy = json.loads(response["body"])
    assert policy["Role"] == role_arn
    assert policy["HomeDirectoryDetails"] == home_directory_details
    assert policy["HomeDirectoryType"] == "LOGICAL"
