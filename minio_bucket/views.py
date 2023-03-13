import logging
import subprocess
import json
from secrets import token_urlsafe
from http import HTTPStatus
import tempfile

from pydantic import BaseModel

from minio_bucket import app, config


# TODO: fix logging output with gunicorn
logger = logging.getLogger(__name__)

ALIAS = "minioServer"


@app.on_event("startup")
async def setup_minio_alias():
    # create a new alias for future use
    subprocess.run([
        "./mc",
        "alias",
        "set",
        ALIAS,
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

    # create the bucket
    subprocess.run([
        "./mc",
        "mb",
        f"{ALIAS}/{data.bucketName}",
    ])

    # creating new user and generating credentials
    user = "user-" + token_urlsafe(10)
    password = token_urlsafe(16)

    # create a new user with the provided credentials
    logger.info(f"Creating user {user}")
    subprocess.run([
        "./mc",
        "admin",
        "user",
        "add",
        ALIAS,
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

    with tempfile.NamedTemporaryFile(mode="wt", suffix=".json") as outfile:
        json.dump(standard_policy, outfile)
        outfile.seek(0)

        logger.info(
            f"Creating policy {data.bucketName}-policy at {outfile.name}"
        )
        # create a new policy
        subprocess.run([
            "./mc",
            "admin",
            "policy",
            "add",
            ALIAS,
            f"{data.bucketName}-policy",
            outfile.name
        ])

    # set the policy for the user
    logger.info(f"Setting policy {data.bucketName}-policy for user {user}")
    subprocess.run([
        "./mc",
        "admin",
        "policy",
        "set",
        ALIAS,
        f"{data.bucketName}-policy",
        f"user={user}"
    ])

    credentials = {
        "bucketname": data.bucketName,
        "access_key": user,
        "access_secret": password,
        "projectid": ""
    }
    return credentials
