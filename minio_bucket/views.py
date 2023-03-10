import logging
import subprocess
import json
from secrets import token_urlsafe
from http import HTTPStatus



from pydantic import BaseModel

from minio_bucket import app, config


# TODO: fix logging output with gunicorn
logger = logging.getLogger(__name__)

CONTAINER_REGISTRY_SECRET_NAME = "container-registry"


@app.on_event("startup")
async def setup_minio_alias():
    subprocess.run([
        "./mc", "alias",
        "set", "minioServer",
        config.MINIO_SERVER_ENDPOINT,
        config.MINIO_ROOT_USER,
        config.MINIO_ROOT_PASSWORD
    ])


class BucketCredentials(BaseModel):
    bucketName: str
    secretName: str
    secretNamespace: str


@app.post("/bucket", status_code=HTTPStatus.OK)
async def create_minio_bucket(data: BucketCredentials) -> None:
    logger.info(f"Creating bucket in namespace {data.bucketName}")

    subprocess.run([
        "./mc", "mb",
        f"minioServer/{data.bucketName}",

    ])

    # creating new user and generating credentials
    user = "user-" + token_urlsafe(10)
    password = token_urlsafe(16)
    subprocess.run([
        "./mc", "admin",
        "user", "add", "minioServer",
        user,
        password
    ])

    # creating the policy and assigning it to the user
    standard_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": [
                    "s3:ListBucket",
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:DeleteObject"
                ],
                "Effect": "Allow",
                "Resource": [
                    f"arn:aws:s3:::{data.bucketName}/*",
                    f"arn:aws:s3:::{data.bucketName}"
                ],
                "Sid": "BucketAccessForUser"
            }
        ]
    }

    with open(f"/tmp/{data.bucketName}-policy.json", "w") as outfile:
        json.dump(standard_policy, outfile)

    subprocess.run([
        "./mc", "admin",
        "policy", "add", "minioServer",
        f"{data.bucketName}-policy",
        f"/tmp/{data.bucketName}-policy.json"
    ])

    subprocess.run([
        "./mc", "admin",
        "policy", "set", "minioServer",
        f"{data.bucketName}-policy",
        f"user={user}"
    ])

    credentials = {
        "bucketname": data.bucketName,
        "access": user,
        "secret": password,
        "projectid": ""
    }
    return credentials
