import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="sls_website",
    version="0.0.1",

    description="Full-stack Serverless Website Demonstration",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="Renato Byrro",
    author_email="renato@byrro.dev",

    package_dir={"": "sls_website"},
    packages=setuptools.find_packages(where="sls_website"),

    install_requires=[
        "aws-cdk.core==1.51.0",
        "aws-cdk.aws-apigateway==1.51.0",
        "aws-cdk.aws-athena==1.51.0",
        "aws-cdk.aws-cloudfront==1.51.0",
        "aws-cdk.aws-dynamodb==1.51.0",
        "aws-cdk.aws-glue==1.51.0",
        "aws-cdk.aws-iam==1.51.0",
        "aws-cdk.aws-kinesisfirehose==1.51.0",
        "aws-cdk.aws-lambda==1.51.0",
        "aws-cdk.aws-lambda-destinations==1.51.0",
        "aws-cdk.aws-lambda-event-sources==1.51.0",
        "aws-cdk.aws-logs==1.50",
        "aws-cdk.aws-s3==1.51.0",
        "aws-cdk.aws-s3-deployment==1.51.0",
        "aws-cdk.aws-sqs==1.51.0",
        "boto3==1.14.11",
        "pytest==5.4.3",
    ],

    python_requires=">=3.8",

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "License :: OSI Approved :: Apache Software License",

        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",

        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
