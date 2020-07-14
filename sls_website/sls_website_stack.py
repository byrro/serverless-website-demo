#! /usr/bin/python3.8 Python3.8
import json

from aws_cdk import (
    core,
    aws_apigateway,
    aws_athena,
    aws_cloudfront,
    aws_dynamodb,
    aws_iam,
    aws_glue,
    aws_kinesisfirehose as aws_firehose,
    aws_lambda,
    aws_lambda_destinations,
    aws_lambda_event_sources,
    aws_logs,
    aws_s3,
    aws_s3_deployment,
    aws_sqs,
)


class AwsResource():
    pass


class DataSize:

    @classmethod
    def bytes(cls, size):
        return size

    @classmethod
    def kilobytes(cls, size):
        return cls.bytes(size) * 1000

    @classmethod
    def megabytes(cls, size):
        return cls.kilobytes(size) * 1000

    @classmethod
    def gigabytes(cls, size):
        return cls.megabytes(size) * 1000

    @classmethod
    def terabytes(cls, size):
        return cls.gigabytes(size) * 1000


class SlsBlogStack(core.Stack):

    def __init__(
            self,
            scope: core.Construct,
            id: str,
            env: core.Environment,
            **kwargs,
            ) -> None:
        super().__init__(scope, id, **kwargs)

        # S3 bucket to store website static files (HTML, CSS, JS...)
        static_bucket = aws_s3.Bucket(
            self,
            'WebsiteStaticS3Bucket',
            bucket_name='slsblog-website-static',
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        cdn_logs_bucket = aws_s3.Bucket(
            self,
            'CDNLogsS3Bucket',
            bucket_name='slsblog-cdn-logs',
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        # CloudFront origin identity to associate with the S3 bucket
        origin = aws_cloudfront.OriginAccessIdentity(
            self,
            'SlsBlogS3OriginAccessIdentity',
            comment='Associated with serverless website static S3 bucket',
        )

        self.cdn = aws_cloudfront.CloudFrontWebDistribution(
            self,
            'SlsBlogCDN',
            comment='CDN for a full-stack serverless website',
            origin_configs=[
                aws_cloudfront.SourceConfiguration(
                    s3_origin_source=aws_cloudfront.S3OriginConfig(
                        s3_bucket_source=static_bucket,
                        origin_access_identity=origin,
                    ),
                    behaviors=[
                        aws_cloudfront.Behavior(
                            is_default_behavior=True,
                            min_ttl=core.Duration.hours(1),
                            max_ttl=core.Duration.hours(24),
                            default_ttl=core.Duration.hours(1),
                            compress=True,
                        )
                    ],
                )
            ],
            default_root_object='index.html',
            enable_ip_v6=True,
            http_version=aws_cloudfront.HttpVersion.HTTP2,
            logging_config=aws_cloudfront.LoggingConfiguration(
                bucket=cdn_logs_bucket,
                include_cookies=True,
            ),
            price_class=aws_cloudfront.PriceClass.PRICE_CLASS_100,
            viewer_protocol_policy=aws_cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,  # NOQA
        )

        aws_s3_deployment.BucketDeployment(
            self,
            'SlsBlogStaticS3Deployment',
            sources=[aws_s3_deployment.Source.asset('website_static')],
            destination_bucket=static_bucket,
            distribution=self.cdn,
        )


class SlsBlogApiStack(core.Stack):

    def __init__(
            self,
            scope: core.Construct,
            id: str,
            env: core.Environment,
            blog_static_stack: core.Stack,
            **kwargs,
            ) -> None:
        super().__init__(scope, id, **kwargs)

        self.static_stack = blog_static_stack

        # AWS Resources Declaration

        # SQS Queues
        self.queue_ddb_streams_dlq = None  # Dead-letter-queue for DDB streams

        # DynamoDB Tables
        self.ddb_table_blog = None  # Single-table for all blog content

        # DynamoDB Event Sources
        self.ddb_source_blog = None  # Blog table streams source

        # DynamoDB Indexes
        self.ddb_gsi_latest = None  # GSI ordering articles by timestamp

        # Lambda Functions
        self.lambda_blog = None  # Serves requests to the blog public API
        self.lambda_stream_reader = None  # Processes DynamoDB streams

        # REST APIs
        self.rest_api_blog = None  # REST API for the Blog

        # Create CDK resources
        self.create_cdk_resources()

    def create_cdk_resources(self) -> None:
        self.create_queues()
        self.create_dynamodb()
        self.create_lambdas()
        self.create_rest_apis()
        self.grant_dynamodb_permissions()

    def create_queues(self) -> None:
        '''SQS Queues
        '''
        self.queue_ddb_streams_dlq = aws_sqs.Queue(
            self,
            'sls-blog-dynamo-streams-dlq',
            retention_period=core.Duration.days(14),  # Max supported by SQS
            visibility_timeout=core.Duration.minutes(15),  # Max Lambda timeout
        )

    def create_dynamodb(self) -> None:
        '''DynamoDB Tables and Event Sources
        '''
        # DynamoDB Table Attributes
        self.ddb_attr_time_to_live = 'time-to-live'

        # DynamoDB Parameters
        self.ddb_param_max_parallel_streams = 5

        # Single-table to store blog content
        self.ddb_table_blog = aws_dynamodb.Table(
            self,
            'sls-blog-dynamo-table',
            partition_key=aws_dynamodb.Attribute(
                name='id',
                type=aws_dynamodb.AttributeType.STRING,
            ),
            billing_mode=aws_dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=core.RemovalPolicy.DESTROY,
            time_to_live_attribute=self.ddb_attr_time_to_live,
            stream=aws_dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        # GSI to query blog content by item (type) and ordered by time
        self.ddb_gsi_latest = 'latest-blogs'

        self.ddb_table_blog.add_global_secondary_index(
            index_name=self.ddb_gsi_latest,
            partition_key=aws_dynamodb.Attribute(
                name='item-type',
                type=aws_dynamodb.AttributeType.STRING,
            ),
            sort_key=aws_dynamodb.Attribute(
                name='publish-timestamp',
                type=aws_dynamodb.AttributeType.NUMBER,
            ),
            projection_type=aws_dynamodb.ProjectionType.ALL,
        )

        # Generate streams from modifications to the "blog" DDB Table
        self.ddb_source_blog = aws_lambda_event_sources.DynamoEventSource(
            table=self.ddb_table_blog,
            starting_position=aws_lambda.StartingPosition.LATEST,
            batch_size=500,
            max_batching_window=core.Duration.seconds(60),
            parallelization_factor=self.ddb_param_max_parallel_streams,
            retry_attempts=2,
            on_failure=aws_lambda_destinations.SqsDestination(
                self.queue_ddb_streams_dlq),
        )

    def create_lambdas(self) -> None:
        '''Lambda Functions
        '''
        self.lambda_param_max_concurrency = 5

        self.lambda_blog = aws_lambda.Function(
            self,
            'api_backend',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            code=aws_lambda.Code.asset('lambda_blog'),
            handler='blog.handler',
            memory_size=1024,
            timeout=core.Duration.seconds(15),
            log_retention=aws_logs.RetentionDays.ONE_MONTH,
            reserved_concurrent_executions=self.lambda_param_max_concurrency,
            environment={
                'DYNAMODB_TABLE_NAME': self.ddb_table_blog.table_name,
                'DYNAMODB_LATEST_ARTICLES_INDEX': self.ddb_gsi_latest,
                'DYNAMODB_TTL_ATTR_NAME': self.ddb_attr_time_to_live,
                'DYNAMODB_TTL_DURATION': str(60*60*24),  # 24 hours
                'STATIC_WEBSITE_DOMAIN': self.static_stack.cdn.domain_name,
            },
        )

        self.lambda_streams_reader = aws_lambda.Function(
            self,
            'streams_reader',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            code=aws_lambda.Code.asset('lambda_streams'),
            handler='streams_reader.handler',
            memory_size=1024,
            timeout=core.Duration.seconds(90),
            log_retention=aws_logs.RetentionDays.ONE_WEEK,
            reserved_concurrent_executions=self.ddb_param_max_parallel_streams,
            events=[self.ddb_source_blog],
            environment={},
        )

    def create_rest_apis(self) -> None:
        '''Rest API Gateway integrations with Lambda
        '''
        self.rest_api_blog = aws_apigateway.LambdaRestApi(
            self,
            'sls-blog-rest-api-gateway',
            handler=self.lambda_blog,
            deploy_options=aws_apigateway.StageOptions(
                stage_name='api',
                throttling_rate_limit=self.lambda_param_max_concurrency,
                logging_level=aws_apigateway.MethodLoggingLevel('INFO'),
            ),
        )

    def grant_dynamodb_permissions(self) -> None:
        '''Grant permissions to interact with DynamoDB Resources
        '''
        self.ddb_table_blog.grant_read_write_data(self.lambda_blog)


class SlsBlogAnalyticalStack(core.Stack):

    def __init__(
            self,
            scope: core.Construct,
            id: str,
            env: core.Environment,
            blog_api_stack: core.Stack,
            **kwargs,
            ) -> None:
        super().__init__(scope, id, **kwargs)

        self.env = env
        self.api_stack = blog_api_stack

        # AWS Resources Declaration

        # S3 Buckets
        self.bucket_analytical = None  # Dataa lake for the blog content
        self.bucket_backup = None  # Original blog content in JSON format
        self.bucket_likes = None  # Data lake for likes to blog content pieces
        self.bucket_queries = None  # Stores Athena queries

        # Kinesis Firehose Streams
        self.firehose_analytical = None  # Main stream for blog content
        self.firehose_likes = None  # Stream to process blog content likes

        # Glue Databases
        self.glue_db_analytical = None  # Main database for blog content

        # Glue Tables
        self.glue_table_analytical = None  # Linked to the analytical bucket
        self.glue_table_likes = None  # Linked to the likes bucket

        # Athena Resources
        self.athena_workgroup = None  # Workgroup for Athena analytical queries

        # IAM Roles
        self.iam_role_firehose_analytical = None
        self.iam_role_firehose_likes = None

        # CloudWatch Logs Groups
        self.log_group_analytical = None  # Groups logs for the entire stack

        # CloudWatch Logs Streams
        self.log_stream_analytical = None  # Firehose analytical logs
        self.log_stream_backup = None  # Firehose backup logs
        self.log_stream_likes = None  # Firehose likes logs

        # Create CDK resources
        self.create_cdk_resources()

    def create_cdk_resources(self) -> None:
        self.create_buckets()
        self.create_glue_resources()
        self.create_iam_glue()
        self.create_cloudwatch_logs()
        self.create_kinesis_firehose()
        self.additional_firehose_permissions()
        self.allow_lambda_to_access_kinesis()
        self.add_lambda_env_vars()
        self.create_athena_resources()

    def create_buckets(self) -> None:
        '''Creates all S3 Bucket resources
        '''
        # This is the bucket where we'll store content processed by Kinesis
        self.bucket_analytical = aws_s3.Bucket(
            self,
            'sls-blog-analytical',
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        # In this bucket, we'll store the JSON data submitted to the Kinesis
        # Firehose Stream; since items in DynamoDB have a time-to-live, the
        # original data will be kept here for further analysis, if needed
        self.bucket_backup = aws_s3.Bucket(
            self,
            'sls-blog-backup',
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        # This is the bucket where we'll store likes processed by Kinesis
        self.bucket_likes = aws_s3.Bucket(
            self,
            'sls-blog-likes',
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        # In this bucket we'll store API requests info processed by Kinesis
        self.bucket_apirequests = aws_s3.Bucket(
            self,
            'sls-blog-apirequests',
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        # This bucket holds Athena query results
        self.bucket_queries = aws_s3.Bucket(
            self,
            'sls-blog-athena-queries',
            removal_policy=core.RemovalPolicy.DESTROY,
        )

    def create_glue_resources(self) -> None:
        '''Creates Glue Database and Tables
        '''
        if not hasattr(self, 'glue_attr'):
            self.prepare_glue_attr_types()

        col = aws_glue.Column

        # Kinesis and Athena depends on data schema declarations that should
        # be in a Database and Table in AWS Glue
        self.glue_db_analytical = aws_glue.Database(
            self,
            'sls-blog-analytical-db',
            database_name='sls-blog-analytical',
            location_uri=None,
        )

        self.glue_table_analytical = aws_glue.Table(
            self,
            'analytical-table',
            table_name='analytical-table',
            columns=[
                col(name='id', type=self.glue_attr_string),
                col(name='publish_timestamp', type=self.glue_attr_timestamp),
                col(name='publisher_email', type=self.glue_attr_string),
                col(name='publisher_name', type=self.glue_attr_string),
                col(name='item_type', type=self.glue_attr_string),
                col(name='title', type=self.glue_attr_string),
                col(name='body', type=self.glue_attr_string),
            ],
            database=self.glue_db_analytical,
            data_format=aws_glue.DataFormat.PARQUET,
            bucket=self.bucket_analytical,
            s3_prefix='kinesis/',
        )

        self.glue_table_likes = aws_glue.Table(
            self,
            'likes-table',
            table_name='likes-table',
            columns=[
                col(name='id', type=self.glue_attr_string),
                col(name='like', type=self.glue_attr_integer),
            ],
            database=self.glue_db_analytical,
            data_format=aws_glue.DataFormat.PARQUET,
            bucket=self.bucket_likes,
            s3_prefix='kinesis/',
        )

        self.glue_table_apirequests = aws_glue.Table(
            self,
            'apirequests-table',
            table_name='apirequests-table',
            columns=[
                col(name='id', type=self.glue_attr_string),
                col(name='item_type', type=self.glue_attr_string),
                col(name='http_method', type=self.glue_attr_string),
                col(name='timestamp', type=self.glue_attr_timestamp),
                col(name='datetime', type=self.glue_attr_date),
                col(name='ip_address', type=self.glue_attr_string),
                col(name='user_agent', type=self.glue_attr_string),
                col(name='origin', type=self.glue_attr_string),
                col(name='country_code', type=self.glue_attr_string),
                col(name='device_type', type=self.glue_attr_string),
                col(name='action', type=self.glue_attr_string),
                col(name='article_id', type=self.glue_attr_string),
            ],
            database=self.glue_db_analytical,
            data_format=aws_glue.DataFormat.PARQUET,
            bucket=self.bucket_apirequests,
            s3_prefix='kinesis/',
        )

    def prepare_glue_attr_types(self) -> None:
        '''Prepare Glue data types for Table schema declarations
        '''
        tp = aws_glue.Type

        self.glue_attr = True

        self.glue_attr_string = tp(input_string='string', is_primitive=True)
        self.glue_attr_integer = tp(input_string='int', is_primitive=True)
        self.glue_attr_date = tp(input_string='date', is_primitive=True)
        self.glue_attr_timestamp = tp(input_string='timestamp',
                                      is_primitive=True)

    def create_iam_glue(self) -> None:
        '''Prepare Roles for Kinesis Firehose with Glue permissions

        Kinesis will need permission to access the Glue Database and Table in
        order to be deployed and to parse incoming data, so we'll pack those
        permissions in a custom managed IAM policy
        '''
        firehose_service_principal = aws_iam.ServicePrincipal(
            service='firehose.amazonaws.com',
        )

        iam_analytical_statement = aws_iam.PolicyStatement(
            actions=[
                'glue:GetTable',
                'glue:GetTableVersion',
                'glue:GetTableVersions',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                self.glue_db_analytical.catalog_arn,
                self.glue_db_analytical.database_arn,
                self.glue_table_analytical.table_arn,
            ],
        )

        analytical_policy_document = aws_iam.PolicyDocument(
            statements=[
                iam_analytical_statement,
            ],
        )

        analytical_policy = aws_iam.ManagedPolicy(
            self,
            'sls-blog-analytical-glue-permissions',
            description='Permissions for a Kinesis Firehose Stream to access '
                        'the Glue "analytical" Database and Table',
            document=analytical_policy_document,
        )

        self.iam_role_firehose_analytical = aws_iam.Role(
            self,
            'sls-blog-firehose-analytical-role',
            assumed_by=firehose_service_principal,
            description='Assumed by Kinesis Firehose "analytical" to access '
                        'the Glue "analytical" Database and Table',
            max_session_duration=core.Duration.hours(12),
            managed_policies=[
                analytical_policy,
            ],
        )

        iam_likes_statement = aws_iam.PolicyStatement(
            actions=[
                'glue:GetTable',
                'glue:GetTableVersion',
                'glue:GetTableVersions',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                self.glue_db_analytical.catalog_arn,
                self.glue_db_analytical.database_arn,
                self.glue_table_likes.table_arn,
            ],
        )

        likes_policy_document = aws_iam.PolicyDocument(
            statements=[
                iam_likes_statement,
            ],
        )

        likes_policy = aws_iam.ManagedPolicy(
            self,
            'sls-blog-likes-glue-permissions',
            description='Permissions for a Kinesis Firehose Stream to access '
                        'the Glue "analytical" Database and "likes" Table',
            document=likes_policy_document,
        )

        self.iam_role_firehose_likes = aws_iam.Role(
            self,
            'sls-blog-firehose-likes-role',
            assumed_by=firehose_service_principal,
            description='Assumed by Kinesis Firehose "likes" to access '
                        'the Glue "analytical" Database and "likes" Table',
            max_session_duration=core.Duration.hours(12),
            managed_policies=[
                likes_policy,
            ],
        )

        iam_apirequests_statement = aws_iam.PolicyStatement(
            actions=[
                'glue:GetTable',
                'glue:GetTableVersion',
                'glue:GetTableVersions',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                self.glue_db_analytical.catalog_arn,
                self.glue_db_analytical.database_arn,
                self.glue_table_apirequests.table_arn,
            ],
        )

        apirequests_policy_document = aws_iam.PolicyDocument(
            statements=[
                iam_apirequests_statement,
            ],
        )

        apirequests_policy = aws_iam.ManagedPolicy(
            self,
            'sls-blog-apirequestss-glue-permissions',
            description='Permissions for a Kinesis Firehose Stream to access '
                        'the Glue "analytical" DB and "apirequests" Table',
            document=apirequests_policy_document,
        )

        self.iam_role_firehose_apirequests = aws_iam.Role(
            self,
            'sls-blog-firehose-apirequests-role',
            assumed_by=firehose_service_principal,
            description='Assumed by Kinesis Firehose "apirequests" to access '
                        'the Glue "analytical" DB and "apirequests" Table',
            max_session_duration=core.Duration.hours(12),
            managed_policies=[
                apirequests_policy,
            ],
        )

    def create_cloudwatch_logs(self) -> None:
        '''CloudWatch Logs Groups and Streams for Kinesis Firehose Streams
        '''
        # Create Log Group and Stream in CloudWatch to monitor Kinesis Firehose
        self.log_group_analytical = aws_logs.LogGroup(
            self,
            'kinesis-firehose-analytical',
            removal_policy=core.RemovalPolicy.DESTROY,
            retention=aws_logs.RetentionDays.ONE_WEEK,
        )

        self.log_stream_analytical = self.log_group_analytical.add_stream(
            'analytical')
        self.log_stream_backup = self.log_group_analytical.add_stream('backup')
        self.log_stream_likes = self.log_group_analytical.add_stream('likes')
        self.log_stream_apirequests = self.log_group_analytical.add_stream(
            'apirequests')

        self.log_stream_analytical.removal_policy = core.RemovalPolicy.DESTROY
        self.log_stream_backup.removal_policy = core.RemovalPolicy.DESTROY
        self.log_stream_likes.removal_policy = core.RemovalPolicy.DESTROY
        self.log_stream_apirequests.removal_policy = core.RemovalPolicy.DESTROY

    def create_kinesis_firehose(self) -> None:
        '''Kinesis Firehose Streams for blog content processing
        '''
        # Short versions of very(!) long CDK Classes
        Stream = aws_firehose.CfnDeliveryStream

        S3DestConfProp = Stream.S3DestinationConfigurationProperty
        ExtendedS3DestConfProp = Stream.ExtendedS3DestinationConfigurationProperty  # NOQA
        BufferingHintsProp = Stream.BufferingHintsProperty
        CloudWatchLogProp = Stream.CloudWatchLoggingOptionsProperty
        FormatConversionProp = Stream.DataFormatConversionConfigurationProperty
        InputFormatConfProp = Stream.InputFormatConfigurationProperty
        OutputFormatConfProp = Stream.OutputFormatConfigurationProperty
        DeserializerProperty = Stream.DeserializerProperty
        SerializerProperty = Stream.SerializerProperty
        OpenXJsonSerDeProperty = Stream.OpenXJsonSerDeProperty
        ParquetSerDeProperty = Stream.ParquetSerDeProperty
        SchemaConfigProp = Stream.SchemaConfigurationProperty

        # Create the Kinesis Firehose stream that will process blog data and
        # store for Athena querying
        self.firehose_analytical = aws_firehose.CfnDeliveryStream(
            self,
            'sls-blog-firehose-analytical',
            delivery_stream_name='sls-blog-analytical',
            delivery_stream_type='DirectPut',
            extended_s3_destination_configuration=ExtendedS3DestConfProp(
                bucket_arn=self.bucket_analytical.bucket_arn,
                role_arn=self.iam_role_firehose_analytical.role_arn,
                buffering_hints=BufferingHintsProp(
                    interval_in_seconds=60,
                    size_in_m_bs=128,
                ),
                # Kinesis will log its activity to this Log Stream
                cloud_watch_logging_options=CloudWatchLogProp(
                    enabled=True,
                    log_group_name=self.log_group_analytical.log_group_name,
                    log_stream_name=self.log_stream_analytical.log_stream_name,
                ),
                # Data will enter Kinesis in JSON format and will be converted
                # to Apache Parquet format, which is highly efficient for
                # running Athena queries
                data_format_conversion_configuration=FormatConversionProp(
                    enabled=True,
                    input_format_configuration=InputFormatConfProp(
                        deserializer=DeserializerProperty(
                            open_x_json_ser_de=OpenXJsonSerDeProperty(),
                        ),
                    ),
                    output_format_configuration=OutputFormatConfProp(
                        serializer=SerializerProperty(
                            parquet_ser_de=ParquetSerDeProperty(
                                compression='UNCOMPRESSED',
                                enable_dictionary_compression=False,
                            ),
                        ),
                    ),
                    schema_configuration=SchemaConfigProp(
                        database_name=self.glue_db_analytical.database_name,
                        table_name=self.glue_table_analytical.table_name,
                        role_arn=self.iam_role_firehose_analytical.role_arn,
                    ),
                ),
                error_output_prefix='kinesis-error/',
                prefix='kinesis/',
                # The original data received by Kinesis Firehose (in JSON) will
                # be stored in this bucket before converting to Parquet
                s3_backup_mode='Enabled',
                s3_backup_configuration=S3DestConfProp(
                    bucket_arn=self.bucket_backup.bucket_arn,
                    role_arn=self.iam_role_firehose_analytical.role_arn,
                    buffering_hints=BufferingHintsProp(
                        interval_in_seconds=60,
                        size_in_m_bs=128,
                    ),
                    cloud_watch_logging_options=CloudWatchLogProp(
                        enabled=True,
                        log_group_name=self.log_group_analytical.log_group_name,  # NOQA
                        log_stream_name=self.log_stream_backup.log_stream_name,
                    ),
                    error_output_prefix='kinesis-error/',
                    prefix='kinesis/',
                ),
            ),
        )

        # Create the Kinesis Firehose stream that will process likes to content
        # in our blog
        self.firehose_likes = aws_firehose.CfnDeliveryStream(
            self,
            'sls-blog-firehose-likes',
            delivery_stream_name='sls-blog-likes',
            delivery_stream_type='DirectPut',
            extended_s3_destination_configuration=ExtendedS3DestConfProp(
                bucket_arn=self.bucket_likes.bucket_arn,
                role_arn=self.iam_role_firehose_likes.role_arn,
                buffering_hints=BufferingHintsProp(
                    interval_in_seconds=60,
                    size_in_m_bs=128,
                ),
                # Kinesis will log its activity to this Log Stream
                cloud_watch_logging_options=CloudWatchLogProp(
                    enabled=True,
                    log_group_name=self.log_group_analytical.log_group_name,
                    log_stream_name=self.log_stream_likes.log_stream_name,
                ),
                # Data will enter Kinesis in JSON format and will be converted
                # to Apache Parquet format, which is highly efficient for
                # running Athena queries
                data_format_conversion_configuration=FormatConversionProp(
                    enabled=True,
                    input_format_configuration=InputFormatConfProp(
                        deserializer=DeserializerProperty(
                            open_x_json_ser_de=OpenXJsonSerDeProperty(),
                        ),
                    ),
                    output_format_configuration=OutputFormatConfProp(
                        serializer=SerializerProperty(
                            parquet_ser_de=ParquetSerDeProperty(
                                compression='UNCOMPRESSED',
                                enable_dictionary_compression=False,
                            ),
                        ),
                    ),
                    schema_configuration=SchemaConfigProp(
                        database_name=self.glue_db_analytical.database_name,
                        table_name=self.glue_table_likes.table_name,
                        role_arn=self.iam_role_firehose_likes.role_arn,
                    ),
                ),
                error_output_prefix='kinesis-error/',
                prefix='kinesis/',
                # Backing up individual likes won't add much meaningful data
                s3_backup_mode='Disabled',
            ),
        )

        # Create the Kinesis Firehose stream that will process api requests
        # from the blog
        self.firehose_apirequests = aws_firehose.CfnDeliveryStream(
            self,
            'sls-blog-firehose-apirequests',
            delivery_stream_name='sls-blog-apirequests',
            delivery_stream_type='DirectPut',
            extended_s3_destination_configuration=ExtendedS3DestConfProp(
                bucket_arn=self.bucket_apirequests.bucket_arn,
                role_arn=self.iam_role_firehose_apirequests.role_arn,
                buffering_hints=BufferingHintsProp(
                    interval_in_seconds=60,
                    size_in_m_bs=128,
                ),
                # Kinesis will log its activity to this Log Stream
                cloud_watch_logging_options=CloudWatchLogProp(
                    enabled=True,
                    log_group_name=self.log_group_analytical.log_group_name,
                    log_stream_name=self.log_stream_apirequests.log_stream_name,  # NOQA
                ),
                # Data will enter Kinesis in JSON format and will be converted
                # to Apache Parquet format, which is highly efficient for
                # running Athena queries
                data_format_conversion_configuration=FormatConversionProp(
                    enabled=True,
                    input_format_configuration=InputFormatConfProp(
                        deserializer=DeserializerProperty(
                            open_x_json_ser_de=OpenXJsonSerDeProperty(),
                        ),
                    ),
                    output_format_configuration=OutputFormatConfProp(
                        serializer=SerializerProperty(
                            parquet_ser_de=ParquetSerDeProperty(
                                compression='UNCOMPRESSED',
                                enable_dictionary_compression=False,
                            ),
                        ),
                    ),
                    schema_configuration=SchemaConfigProp(
                        database_name=self.glue_db_analytical.database_name,
                        table_name=self.glue_table_apirequests.table_name,
                        role_arn=self.iam_role_firehose_apirequests.role_arn,
                    ),
                ),
                error_output_prefix='kinesis-error/',
                prefix='kinesis/',
                # Backing up individual api requests won't be valuable
                s3_backup_mode='Disabled',
            ),
        )

    def additional_firehose_permissions(self) -> None:
        '''Attaches additional policies to the Kinesis Firehose Roles

        The Role needed to be created with the Glue policy first, because it
        was required for the deployment process. Now we add the rest of the
        permissions, after all resources are declared
        '''
        # Permissions for Firehose Analytical
        iam_s3_analytical_statement = aws_iam.PolicyStatement(
            actions=[
                's3:AbortMultipartUpload',
                's3:GetBucketLocation',
                's3:GetObject',
                's3:ListBucket',
                's3:ListBucketMultipartUploads',
                's3:PutObject',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                # Main bucket for Athena queries (Parquet data)
                self.bucket_analytical.bucket_arn,
                f'{self.bucket_analytical.bucket_arn}/*',

                # Backup bucket (original JSON data)
                self.bucket_backup.bucket_arn,
                f'{self.bucket_backup.bucket_arn}/*',
            ],
        )

        iam_kinesis_analytical_statement = aws_iam.PolicyStatement(
            actions=[
                'kinesis:DescribeStream',
                'kinesis:GetShardIterator',
                'kinesis:GetRecords',
                'kinesis:ListShards',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                f'arn:aws:firehose:{self.env.region}:{self.env.account}:'
                f'deliverystream/{self.firehose_analytical.delivery_stream_name}',  # NOQA
            ],
        )

        iam_logs_analytical_statement = aws_iam.PolicyStatement(
            actions=[
                'logs:PutLogEvents',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                # Log stream for the converted (Parquet) records; please
                # observe that the following lines form a single Log Stream ARN
                f'arn:aws:logs:{self.env.region}:{self.env.account}:'
                f'log-group:{self.log_group_analytical.log_group_name}:'
                f'log-stream:{self.log_stream_analytical.log_stream_name}',
            ],
        )

        iam_logs_backup_statement = aws_iam.PolicyStatement(
            actions=[
                'logs:PutLogEvents',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                # Log stream for the backup (JSON) records; please observe
                # that the following lines form a single Log Stream ARN
                f'arn:aws:logs:{self.env.region}:{self.env.account}:'
                f'log-group:{self.log_group_analytical.log_group_name}:'
                f'log-stream:{self.log_stream_backup.log_stream_name}',
            ],
        )

        analytical_policy_document = aws_iam.PolicyDocument(
            statements=[
                iam_s3_analytical_statement,
                iam_kinesis_analytical_statement,
                iam_logs_analytical_statement,
                iam_logs_backup_statement,
            ],
        )

        analytical_policy = aws_iam.ManagedPolicy(
            self,
            'sls-blog-analytical-s3-logs-permissions',
            description='Permissions to the "analytical" Kinesis Firehose '
                        'Stream to access S3 buckets and Log Streams',
            document=analytical_policy_document,
        )

        analytical_policy.attach_to_role(self.iam_role_firehose_analytical)

        # Permissions for Firehose Likes
        iam_s3_likes_statement = aws_iam.PolicyStatement(
            actions=[
                's3:AbortMultipartUpload',
                's3:GetBucketLocation',
                's3:GetObject',
                's3:ListBucket',
                's3:ListBucketMultipartUploads',
                's3:PutObject',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                # Likes bucket for Athena queries (Parquet data)
                self.bucket_likes.bucket_arn,
                f'{self.bucket_likes.bucket_arn}/*',
            ],
        )

        iam_kinesis_likes_statement = aws_iam.PolicyStatement(
            actions=[
                'kinesis:DescribeStream',
                'kinesis:GetShardIterator',
                'kinesis:GetRecords',
                'kinesis:ListShards',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                f'arn:aws:firehose:{self.env.region}:{self.env.account}:'
                f'deliverystream/{self.firehose_likes.delivery_stream_name}',
            ],
        )

        iam_logs_likes_statement = aws_iam.PolicyStatement(
            actions=[
                'logs:PutLogEvents',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                # Log stream for the likes records; please observe that the
                # following lines form a single Log Stream ARN
                f'arn:aws:logs:{self.env.region}:{self.env.account}:'
                f'log-group:{self.log_group_analytical.log_group_name}:'
                f'log-stream:{self.log_stream_likes.log_stream_name}',
            ],
        )

        likes_policy_document = aws_iam.PolicyDocument(
            statements=[
                iam_s3_likes_statement,
                iam_kinesis_likes_statement,
                iam_logs_likes_statement,
            ],
        )

        likes_policy = aws_iam.ManagedPolicy(
            self,
            'sls-blog-likes-s3-logs-permissions',
            description='Permissions to the "likes" Kinesis Firehose Stream '
                        'to access S3 buckets and Log Streams',
            document=likes_policy_document,
        )

        likes_policy.attach_to_role(self.iam_role_firehose_likes)

        # Permissions for Firehose API Requests
        iam_s3_apirequests_statement = aws_iam.PolicyStatement(
            actions=[
                's3:AbortMultipartUpload',
                's3:GetBucketLocation',
                's3:GetObject',
                's3:ListBucket',
                's3:ListBucketMultipartUploads',
                's3:PutObject',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                # apirequests bucket for Athena queries (Parquet data)
                self.bucket_apirequests.bucket_arn,
                f'{self.bucket_apirequests.bucket_arn}/*',
            ],
        )

        iam_kinesis_apirequests_statement = aws_iam.PolicyStatement(
            actions=[
                'kinesis:DescribeStream',
                'kinesis:GetShardIterator',
                'kinesis:GetRecords',
                'kinesis:ListShards',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                f'arn:aws:firehose:{self.env.region}:{self.env.account}:'
                f'deliverystream/{self.firehose_likes.delivery_stream_name}',
            ],
        )

        iam_logs_apirequests_statement = aws_iam.PolicyStatement(
            actions=[
                'logs:PutLogEvents',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                # Log stream for the api requests records; please observe
                # that the following lines form a single Log Stream ARN
                f'arn:aws:logs:{self.env.region}:{self.env.account}:'
                f'log-group:{self.log_group_analytical.log_group_name}:'
                f'log-stream:{self.log_stream_apirequests.log_stream_name}',
            ],
        )

        apirequests_policy_document = aws_iam.PolicyDocument(
            statements=[
                iam_s3_apirequests_statement,
                iam_kinesis_apirequests_statement,
                iam_logs_apirequests_statement,
            ],
        )

        apirequests_policy = aws_iam.ManagedPolicy(
            self,
            'sls-blog-apirequests-s3-logs-permissions',
            description='Permissions for the "apirequests" Kinesis Firehose '
                        'to access S3 buckets and Log Streams',
            document=apirequests_policy_document,
        )

        apirequests_policy.attach_to_role(self.iam_role_firehose_apirequests)

    def allow_lambda_to_access_kinesis(self) -> None:
        '''Additional permissions needed by Lambda functions to access Kinesis
        '''
        iam_kinesis_statement = aws_iam.PolicyStatement(
            actions=[
                'firehose:PutRecord',
                'firehose:PutRecordBatch',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                f'arn:aws:firehose:{self.env.region}:{self.env.account}:'
                f'deliverystream/{self.firehose_analytical.delivery_stream_name}',  # NOQA

                f'arn:aws:firehose:{self.env.region}:{self.env.account}:'
                f'deliverystream/{self.firehose_likes.delivery_stream_name}',
            ],
        )

        iam_kinesis_document = aws_iam.PolicyDocument(
            statements=[
                iam_kinesis_statement,
            ],
        )

        policy = aws_iam.ManagedPolicy(
            self,
            'sls-blog-lambda-to-kinesis-permissions',
            description='Permissions for a Lambda function to put records in '
                        'Kinesis Firehose Streams',
            document=iam_kinesis_document,
        )

        self.api_stack.lambda_streams_reader.role.add_managed_policy(policy)

        iam_kinesis_statement_apirequests = aws_iam.PolicyStatement(
            actions=[
                'firehose:PutRecord',
                'firehose:PutRecordBatch',
            ],
            effect=aws_iam.Effect.ALLOW,
            resources=[
                f'arn:aws:firehose:{self.env.region}:{self.env.account}:'
                f'deliverystream/{self.firehose_apirequests.delivery_stream_name}',  # NOQA
            ],
        )

        iam_kinesis_document_apirequests = aws_iam.PolicyDocument(
            statements=[
                iam_kinesis_statement_apirequests,
            ],
        )

        policy_apirequests = aws_iam.ManagedPolicy(
            self,
            'sls-blog-lambda-to-kinesis-permissions-apirequests',
            description='Permissions for a Lambda function to put records in '
                        'Kinesis Firehose Streams',
            document=iam_kinesis_document_apirequests,
        )

        self.api_stack.lambda_streams_reader.role.add_managed_policy(
            policy_apirequests)

    def add_lambda_env_vars(self) -> None:
        '''Declare Kinesis Firehose info as Lambda environment variables
        '''
        # Add Kinesis Firehose Streams names to Lambda Streams Reader env
        self.api_stack.lambda_streams_reader.add_environment(
            'FIREHOSE_ANALYTICAL_STREAM_NAME',
            self.firehose_analytical.delivery_stream_name,
        )

        self.api_stack.lambda_streams_reader.add_environment(
            'FIREHOSE_LIKES_STREAM_NAME',
            self.firehose_likes.delivery_stream_name,
        )

        self.api_stack.lambda_streams_reader.add_environment(
            'FIREHOSE_APIREQUESTS_STREAM_NAME',
            self.firehose_apirequests.delivery_stream_name,
        )

    def create_athena_resources(self) -> None:
        self.athena_workgroup = aws_athena.CfnWorkGroup(
            self,
            'SlsBlogAthenaWorkgroup',
            name='sls-blog-athena-workgroup',
            description='Serverless Website demo project (by Dashbird)',
            recursive_delete_option=True,
            state='ENABLED',
            work_group_configuration_updates=core.CfnJson(
                self,
                'sls-blog-workgroup-config-updates',
                value={
                    'EnforceWorkGroupConfiguration': True,
                    'BytesScannedCutoffPerQuery': DataSize.gigabytes(1),
                    'PublishCloudWatchMetricsEnabled': True,
                    'ResultConfigurationUpdates': {
                        'OutputLocation':
                            f's3://{self.bucket_queries.bucket_name}/',
                    },
                },
            ),
        )
