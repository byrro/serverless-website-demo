#!/usr/bin/python3.8 python3.8
import os

from aws_cdk import core

from sls_website.sls_website_stack import (
    SlsBlogStack,
    SlsBlogApiStack,
    SlsBlogAnalyticalStack,
)


try:
    AWS_ACCOUNT_ID = os.environ['AWS_ACCOUNT_ID']
except KeyError as error:
    raise KeyError(
        'Please set "AWS_ACCOUNT_ID" environment variable with the AWS '
        'account ID where the CDK Stack is supposed to be deployed.'
    ) from error


app = core.App()

env = core.Environment(
    account=AWS_ACCOUNT_ID,
    region='us-east-1',
)


# Static blog website
blog_static_stack = SlsBlogStack(
    app,
    'sls-blog',
    env=env,
)

# Backend blog API
blog_api_stack = SlsBlogApiStack(
    app,
    'sls-blog-api',
    env=env,
    blog_static_stack=blog_static_stack,
)

# Analytical resources
SlsBlogAnalyticalStack(
    app,
    'sls-blog-analytical',
    env=env,
    blog_api_stack=blog_api_stack,
)

app.synth()
