#! /usr/bin/python3.8 Python3.8
import pytest


@pytest.fixture(scope='function', autouse=True)
def load_environment_vars(monkeypatch):
    monkeypatch.setenv(
        'FIREHOSE_ANALYTICAL_STREAM_NAME', 'firehose-analytical')
    monkeypatch.setenv('FIREHOSE_LIKES_STREAM_NAME', 'firehose-likes')


@pytest.fixture()
def sample_ddb_streams():
    return {
        "Records": [
            {
                "eventID": "22913059a4e7bb091988bafeccd304c6",
                "eventName": "INSERT",
                "eventVersion": "1.1",
                "eventSource": "aws:dynamodb",
                "awsRegion": "us-east-1",
                "dynamodb": {
                    "ApproximateCreationDateTime": 1594596504,
                    "Keys": {
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        }
                    },
                    "NewImage": {
                        "time-to-live": {
                            "N": "1594682904"
                        },
                        "item-type": {
                            "S": "blog-article"
                        },
                        "publisher-name": {
                            "S": "Renato Byrro"
                        },
                        "publish-timestamp": {
                            "N": "1594596504"
                        },
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        },
                        "body": {
                            "S": "Lorem ipsum"
                        },
                        "publisher-email": {
                            "S": "renato@byrro.dev"
                        },
                        "title": {
                            "S": "Hello world!"
                        },
                        "likes": {
                            "N": "0"
                        }
                    },
                    "SequenceNumber": "4827400000000015091308973",
                    "SizeBytes": 228,
                    "StreamViewType": "NEW_AND_OLD_IMAGES"
                },
                "eventSourceARN": "arn:aws:dynamodb:us-east-1:1234567890:table/sls-blog-api-slsblogdynamotable2DB89FEB-18HZJCQJL6B8B/stream/2020-07-11T22:39:48.714"  # NOQA
            },
            {
                "eventID": "4dc1735c9f1700aa04e8b41dccda0fe4",
                "eventName": "MODIFY",
                "eventVersion": "1.1",
                "eventSource": "aws:dynamodb",
                "awsRegion": "us-east-1",
                "dynamodb": {
                    "ApproximateCreationDateTime": 1594596509,
                    "Keys": {
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        }
                    },
                    "NewImage": {
                        "time-to-live": {
                            "N": "1594682904"
                        },
                        "item-type": {
                            "S": "blog-article"
                        },
                        "publisher-name": {
                            "S": "Renato Byrro"
                        },
                        "publish-timestamp": {
                            "N": "1594596504"
                        },
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        },
                        "body": {
                            "S": "Lorem ipsum"
                        },
                        "publisher-email": {
                            "S": "renato@byrro.dev"
                        },
                        "title": {
                            "S": "Hello world!"
                        },
                        "likes": {
                            "N": "1"
                        }
                    },
                    "OldImage": {
                        "time-to-live": {
                            "N": "1594682904"
                        },
                        "item-type": {
                            "S": "blog-article"
                        },
                        "publisher-name": {
                            "S": "Renato Byrro"
                        },
                        "publish-timestamp": {
                            "N": "1594596504"
                        },
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        },
                        "body": {
                            "S": "Lorem ipsum"
                        },
                        "publisher-email": {
                            "S": "renato@byrro.dev"
                        },
                        "title": {
                            "S": "Hello world!"
                        },
                        "likes": {
                            "N": "0"
                        }
                    },
                    "SequenceNumber": "4827500000000015091312048",
                    "SizeBytes": 423,
                    "StreamViewType": "NEW_AND_OLD_IMAGES"
                },
                "eventSourceARN": "arn:aws:dynamodb:us-east-1:1234567890:table/sls-blog-api-slsblogdynamotable2DB89FEB-18HZJCQJL6B8B/stream/2020-07-11T22:39:48.714"  # NOQA
            },
            {
                "eventID": "03e30497caa63b756f0b41b7994e31e7",
                "eventName": "MODIFY",
                "eventVersion": "1.1",
                "eventSource": "aws:dynamodb",
                "awsRegion": "us-east-1",
                "dynamodb": {
                    "ApproximateCreationDateTime": 1594596510,
                    "Keys": {
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        }
                    },
                    "NewImage": {
                        "time-to-live": {
                            "N": "1594682904"
                        },
                        "item-type": {
                            "S": "blog-article"
                        },
                        "publisher-name": {
                            "S": "Renato Byrro"
                        },
                        "publish-timestamp": {
                            "N": "1594596504"
                        },
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        },
                        "body": {
                            "S": "Lorem ipsum"
                        },
                        "publisher-email": {
                            "S": "renato@byrro.dev"
                        },
                        "title": {
                            "S": "Hello world!"
                        },
                        "likes": {
                            "N": "2"
                        }
                    },
                    "OldImage": {
                        "time-to-live": {
                            "N": "1594682904"
                        },
                        "item-type": {
                            "S": "blog-article"
                        },
                        "publisher-name": {
                            "S": "Renato Byrro"
                        },
                        "publish-timestamp": {
                            "N": "1594596504"
                        },
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        },
                        "body": {
                            "S": "Lorem ipsum"
                        },
                        "publisher-email": {
                            "S": "renato@byrro.dev"
                        },
                        "title": {
                            "S": "Hello world!"
                        },
                        "likes": {
                            "N": "1"
                        }
                    },
                    "SequenceNumber": "4827600000000015091312265",
                    "SizeBytes": 424,
                    "StreamViewType": "NEW_AND_OLD_IMAGES"
                },
                "eventSourceARN": "arn:aws:dynamodb:us-east-1:1234567890:table/sls-blog-api-slsblogdynamotable2DB89FEB-18HZJCQJL6B8B/stream/2020-07-11T22:39:48.714"  # NOQA
            },
            {
                "eventID": "7598ab43a2f4e8b5f577adb7c6c89869",
                "eventName": "MODIFY",
                "eventVersion": "1.1",
                "eventSource": "aws:dynamodb",
                "awsRegion": "us-east-1",
                "dynamodb": {
                    "ApproximateCreationDateTime": 1594596510,
                    "Keys": {
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        }
                    },
                    "NewImage": {
                        "time-to-live": {
                            "N": "1594682904"
                        },
                        "item-type": {
                            "S": "blog-article"
                        },
                        "publisher-name": {
                            "S": "Renato Byrro"
                        },
                        "publish-timestamp": {
                            "N": "1594596504"
                        },
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        },
                        "body": {
                            "S": "Lorem ipsum"
                        },
                        "publisher-email": {
                            "S": "renato@byrro.dev"
                        },
                        "title": {
                            "S": "Hello world!"
                        },
                        "likes": {
                            "N": "3"
                        }
                    },
                    "OldImage": {
                        "time-to-live": {
                            "N": "1594682904"
                        },
                        "item-type": {
                            "S": "blog-article"
                        },
                        "publisher-name": {
                            "S": "Renato Byrro"
                        },
                        "publish-timestamp": {
                            "N": "1594596504"
                        },
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        },
                        "body": {
                            "S": "Lorem ipsum"
                        },
                        "publisher-email": {
                            "S": "renato@byrro.dev"
                        },
                        "title": {
                            "S": "Hello world!"
                        },
                        "likes": {
                            "N": "2"
                        }
                    },
                    "SequenceNumber": "4827700000000015091312311",
                    "SizeBytes": 424,
                    "StreamViewType": "NEW_AND_OLD_IMAGES"
                },
                "eventSourceARN": "arn:aws:dynamodb:us-east-1:1234567890:table/sls-blog-api-slsblogdynamotable2DB89FEB-18HZJCQJL6B8B/stream/2020-07-11T22:39:48.714"  # NOQA
            },
            {
                "eventID": "eefcd432b29133bfd5c1780d1b66b5e3",
                "eventName": "MODIFY",
                "eventVersion": "1.1",
                "eventSource": "aws:dynamodb",
                "awsRegion": "us-east-1",
                "dynamodb": {
                    "ApproximateCreationDateTime": 1594596510,
                    "Keys": {
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        }
                    },
                    "NewImage": {
                        "time-to-live": {
                            "N": "1594682904"
                        },
                        "item-type": {
                            "S": "blog-article"
                        },
                        "publisher-name": {
                            "S": "Renato Byrro"
                        },
                        "publish-timestamp": {
                            "N": "1594596504"
                        },
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        },
                        "body": {
                            "S": "Lorem ipsum"
                        },
                        "publisher-email": {
                            "S": "renato@byrro.dev"
                        },
                        "title": {
                            "S": "Hello world!"
                        },
                        "likes": {
                            "N": "4"
                        }
                    },
                    "OldImage": {
                        "time-to-live": {
                            "N": "1594682904"
                        },
                        "item-type": {
                            "S": "blog-article"
                        },
                        "publisher-name": {
                            "S": "Renato Byrro"
                        },
                        "publish-timestamp": {
                            "N": "1594596504"
                        },
                        "id": {
                            "S": "da4c60a5db7672b2ce71a2d11a0048eb"
                        },
                        "body": {
                            "S": "Lorem ipsum"
                        },
                        "publisher-email": {
                            "S": "renato@byrro.dev"
                        },
                        "title": {
                            "S": "Hello world!"
                        },
                        "likes": {
                            "N": "3"
                        }
                    },
                    "SequenceNumber": "4827800000000015091312450",
                    "SizeBytes": 424,
                    "StreamViewType": "NEW_AND_OLD_IMAGES"
                },
                "eventSourceARN": "arn:aws:dynamodb:us-east-1:1234567890:table/sls-blog-api-slsblogdynamotable2DB89FEB-18HZJCQJL6B8B/stream/2020-07-11T22:39:48.714"  # NOQA
            }
        ]
    }
