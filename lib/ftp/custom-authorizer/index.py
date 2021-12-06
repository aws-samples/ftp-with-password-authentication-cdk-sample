import os
import json
import boto3
import base64
from ipaddress import ip_network, ip_address
from botocore.exceptions import ClientError

# modified the code from this blog: https://aws.amazon.com/blogs/storage/enable-password-authentication-for-aws-transfer-family-using-aws-secrets-manager-updated/

region = os.environ["AWS_REGION"]
# Create a Secrets Manager client
sm_client = boto3.session.Session().client(
    service_name="secretsmanager", region_name=region)


def handler(event, context):
    response = handler_helper(event)
    return {
        'statusCode': 200,
        'body': json.dumps(response)
    }


def handler_helper(event):
    print(event)

    input_serverId = event["pathParameters"]["serverId"]
    input_username = event["pathParameters"]["username"]
    input_protocol = event["queryStringParameters"]["protocol"]
    input_sourceIp = event["requestContext"]["identity"]["sourceIp"]
    input_password = event["headers"].get("Password", "")

    print("ServerId: {}, Username: {}, Protocol: {}, SourceIp: {}"
          .format(input_serverId, input_username, input_protocol, input_sourceIp))

    # Check for password and set authentication type appropriately. No password means SSH auth
    print("Start User Authentication Flow")
    if input_password != "":
        print("Using PASSWORD authentication")
        authentication_type = "PASSWORD"
    else:
        if input_protocol == 'FTP' or input_protocol == 'FTPS':
            print("Empty password not allowed for FTP/S")
            return {}
        print("Using SSH authentication")
        authentication_type = "SSH"

    # Retrieve our user details from the secret. For all key-value pairs stored in SecretManager,
    # checking the protocol-specified secret first, then use generic ones.
    # e.g. If SFTPPassword and Password both exists, will be using SFTPPassword for authentication
    secret = get_secret("ftpSecret/" + input_serverId + "/" + input_username)

    if secret is not None:
        secret_dict = json.loads(secret)
        # Run our password checks
        user_authenticated = authenticate_user(
            authentication_type, secret_dict, input_password, input_protocol)
        # Run sourceIp checks
        ip_match = check_ipaddress(secret_dict, input_sourceIp, input_protocol)

        if user_authenticated and ip_match:
            print("User authenticated, calling build_response with: " +
                  authentication_type)
            return build_response(secret_dict, authentication_type, input_protocol)
        else:
            print("User failed authentication return empty response")
            return {}
    else:
        # Otherwise something went wrong. Most likely the object name is not there
        print("Secrets Manager exception thrown - Returning empty response")
        # Return an empty data response meaning the user was not authenticated
        return {}


def lookup(secret_dict, key, input_protocol):
    if input_protocol + key in secret_dict:
        print("Found protocol-specified {}".format(key))
        return secret_dict[input_protocol + key]
    else:
        return secret_dict.get(key, None)


def check_ipaddress(secret_dict, input_sourceIp, input_protocol):
    accepted_ip_network = lookup(
        secret_dict, "AcceptedIpNetwork", input_protocol)
    if not accepted_ip_network:
        # No IP provided so skip checks
        print("No IP range provided - Skip IP check")
        return True

    net = ip_network(accepted_ip_network)
    if ip_address(input_sourceIp) in net:
        print("Source IP address match")
        return True
    else:
        print("Source IP address not in range")
        return False


def authenticate_user(auth_type, secret_dict, input_password, input_protocol):
    # Function returns True if: auth_type is password and passwords match or auth_type is SSH. Otherwise returns False
    if auth_type == "SSH":
        # Place for additional checks in future
        print("Skip password check as SSH login request")
        return True
    # auth_type could only be SSH or PASSWORD
    else:
        # Retrieve the password from the secret if exists
        password = lookup(secret_dict, "Password", input_protocol)
        if not password:
            print("Unable to authenticate user - No field match in Secret for password")
            return False

        if input_password == password:
            return True
        else:
            print("Unable to authenticate user - Incoming password does not match stored")
            return False


# Build out our response data for an authenticated response
def build_response(secret_dict, auth_type, input_protocol):
    response_data = {}
    # Check for each key value pair. These are required so set to empty string if missing
    role = lookup(secret_dict, "Role", input_protocol)
    if role:
        response_data["Role"] = role
    else:
        print("No field match for role - Set empty string in response")
        response_data["Role"] = ""

    # These are optional so ignore if not present
    policy = lookup(secret_dict, "Policy", input_protocol)
    if policy:
        response_data["Policy"] = policy

    # External Auth providers support chroot and virtual folder assignments so we'll check for that
    home_directory_details = lookup(
        secret_dict, "HomeDirectoryDetails", input_protocol)
    if home_directory_details:
        print("HomeDirectoryDetails found - Applying setting for virtual folders - "
              "Note: Cannot be used in conjunction with key: HomeDirectory")
        response_data["HomeDirectoryDetails"] = home_directory_details
        # If we have a virtual folder setup then we also need to set HomeDirectoryType to "Logical"
        print("Setting HomeDirectoryType to LOGICAL")
        response_data["HomeDirectoryType"] = "LOGICAL"

    # Note that HomeDirectory and HomeDirectoryDetails / Logical mode
    # can't be used together but we're not checking for this
    home_directory = lookup(secret_dict, "HomeDirectory", input_protocol)
    if home_directory:
        print("HomeDirectory found - Note: Cannot be used in conjunction with key: HomeDirectoryDetails")
        response_data["HomeDirectory"] = home_directory

    if auth_type == "SSH":
        public_key = lookup(secret_dict, "PublicKey", input_protocol)
        if public_key:
            response_data["PublicKeys"] = [public_key]
        else:
            # SSH Auth Flow - We don't have keys so we can't help
            print("Unable to authenticate user - No public keys found")
            return {}

    return response_data


def get_secret(id):
    print("Secrets Manager Region: " + region)
    print("Secret Name: " + id)

    try:
        resp = sm_client.get_secret_value(SecretId=id)
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if "SecretString" in resp:
            print("Found Secret String")
            return resp["SecretString"]
        else:
            print("Found Binary Secret")
            return base64.b64decode(resp["SecretBinary"])
    except ClientError as err:
        print("Error Talking to SecretsManager: " + err.response["Error"]["Code"] + ", Message: " +
              err.response["Error"]["Message"])
        return None
