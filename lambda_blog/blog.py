#! /usr/bin/python3.8 Python3.8
from datetime import datetime
import hashlib
import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Union

import boto3
import botocore

from error_handling import CustomException, ErrorMsg


logger = logging.getLogger()
logger.setLevel(logging.WARNING)


MAX_CACHE_AGE: int = 120  # In seconds
CACHE_LATEST_ARTICLES: Dict[str, Union[int, list]] = {
    'last_update': time.time(),
    'articles': [],
}
TIME_TO_LIVE_ATTR_NAME: str = os.environ['DYNAMODB_TTL_ATTR_NAME']
TIME_TO_LIVE_DURATION: int = int(os.environ['DYNAMODB_TTL_DURATION'])


def wrap_handler(handler):
    def inner(event, context):
        print('REQUEST:')
        print(json.dumps(event))

        if event.get('httpMethod') == 'OPTIONS':
            response = {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/plain',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
                },
                'body': '',
            }

        else:
            response = handler(event, context)

        print('RESPONSE:')
        print(json.dumps(response))

        return response

    return inner


@wrap_handler
def handler(event: dict, context: Any):
    status_code: int = 200
    res_body: Dict[str, Any] = {}

    try:
        try:
            store_http_request_info(event=event)
        except Exception as error:
            logger.error(ErrorMsg.STORE_HTTP_REQUEST_INFO)
            logger.exception(error)

        try:
            action: str = event['queryStringParameters']['action']
        except (TypeError, KeyError) as error:
            raise CustomException(ErrorMsg.MISSING_ACTION_PARAM) from error

        res_body['action']: str = action

        try:
            executor: Callable[[dict], dict] = action_mapper(action=action)
        except KeyError as error:
            raise CustomException(ErrorMsg.INVALID_ACTION.format(action)) \
                from error

        results: dict = executor(event=event)

        res_body['message']: str = results['public_message']
        res_body['data']: dict = results.get('public_data')

        if 'status_code' in results:
            status_code: int = results['status_code']

    except CustomException as error:
        logger.exception(error)

        status_code: int = error.status_code
        res_body['error']: str = error.public_message

    except Exception as error:
        logger.exception(error)

        status_code: int = 500
        res_body['error']: str = ErrorMsg.GENERIC_PUBLIC_ERROR

    finally:
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'text/plain',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
            },
            'body': json.dumps(res_body),
        }


def store_http_request_info(*, event: dict) -> None:
    timestamp = round(event['requestContext']['requestTimeEpoch'] / 1000)

    if event['headers']['CloudFront-Is-Desktop-Viewer'] is True:
        device_type = 'Desktop'

    elif event['headers']['CloudFront-Is-Mobile-Viewer'] is True:
        device_type = 'Mobile'

    elif event['headers']['CloudFront-Is-SmartTV-Viewer'] is True:
        device_type = 'SmartTV'

    elif event['headers']['CloudFront-Is-Tablet-Viewer'] is True:
        device_type = 'Tablet'

    else:
        device_type = 'Unknown'

    try:
        body = json.loads(event['body'])
        article_id = body.get('article_id')
    except Exception:
        article_id = None

    client = boto3.client('dynamodb')

    client.put_item(
        TableName=os.environ['DYNAMODB_TABLE_NAME'],
        Item={
            'id': {
                'S': event['requestContext']['requestId'],
            },
            'item-type': {
                'S': 'api-request',
            },
            'http-method': {
                'S': event['httpMethod'],
            },
            'timestamp': {
                'N': str(timestamp),
            },
            'datetime': {
                'S': date_str(timestamp),
            },
            'ip-address': {
                'S': event['requestContext']['identity']['sourceIp'],
            },
            'user-agent': {
                'S': event['requestContext']['identity']['userAgent'],
            },
            'origin': {
                'S': event['headers'].get('origin', ''),
            },
            'country-code': {
                'S': event['headers'].get('CloudFront-Viewer-Country'),
            },
            'device-type': {
                'S': device_type,
            },
            'action': {
                'S': event['queryStringParameters'].get('action'),
            },
            'article-id': {
                'S': article_id,
            },
            # The article will be auto-deleted by Dynamo after certain time
            TIME_TO_LIVE_ATTR_NAME: {
                'N': str(timestamp + TIME_TO_LIVE_DURATION),
            },
        },
        # Make sure we don't override a previously entered article
        ConditionExpression='attribute_not_exists(#id)',
        ExpressionAttributeNames={
            '#id': 'id',
        },
    )


def action_mapper(*, action: str) -> Callable[[dict], dict]:
    mapper: dict = {
        'get-latest-articles': get_latest_articles,
        'publish-article': put_article,
        'like-article': like_article,
    }

    return mapper[action]


def is_cache_valid(
        *,
        now: Optional[Union[int, None]] = None,
        ) -> Union[dict, bool]:
    '''Validates whether articles cache is fresh enough to be used
    '''
    if type(now) is not int:
        now = int(time.time())

    if now < CACHE_LATEST_ARTICLES['last_update'] + MAX_CACHE_AGE:
        return CACHE_LATEST_ARTICLES['articles']

    return False


def update_cache(*, articles: List[Dict[str, Any]]) -> None:
    CACHE_LATEST_ARTICLES['articles'] = articles
    CACHE_LATEST_ARTICLES['last_update']: int = int(time.time())

    return None


def get_latest_articles(*, event: dict):
    if cached_articles := is_cache_valid():
        articles: List[Dict[str, Any]] = cached_articles

    else:
        client = boto3.client('dynamodb')

        response: dict = client.query(
            TableName=os.environ['DYNAMODB_TABLE_NAME'],
            IndexName=os.environ['DYNAMODB_LATEST_ARTICLES_INDEX'],
            Select='ALL_ATTRIBUTES',
            Limit=50,
            ConsistentRead=False,
            ScanIndexForward=False,  # Descending order
            KeyConditionExpression='#partition_key = :article',
            ExpressionAttributeNames={
                '#partition_key': 'item-type',
            },
            ExpressionAttributeValues={
                ':article': {
                    'S': 'blog-article',
                },
            },
        )

        articles: List[Dict[str, Any]] = [
            {
                'id': item['id']['S'],
                'publish-datetime': date_str(item['publish-timestamp']['N']),
                'publisher-email': item['publisher-email']['S'],
                'publisher-name': item['publisher-name']['S'],
                'title': item['title']['S'],
                'body': item['body']['S'],
                'likes': int(item['likes']['N']),
            }
            for item in response['Items']
        ]

        update_cache(articles=articles)

    return {
        'public_message': 'Articles retrieved',
        'public_data': {
            'articles': articles,
        },
    }


def date_str(timestamp: Union[str, int]) -> str:
    if type(timestamp) is str:
        timestamp = int(timestamp)

    date = datetime.fromtimestamp(timestamp)

    return date.strftime('%Y-%m-%d %H:%M (UTC)')


def put_article(*, event: dict):
    publish_timestamp: int = int(time.time())

    try:
        article: Dict[str, str] = json.loads(event['body'])['article']
    except Exception as error:
        raise CustomException(ErrorMsg.UNAVAILABLE_ARTICLE_DATA) from error

    article_id: str = hashlib.md5(
        f'{article["title"]}{article["body"]}'.encode('utf-8')).hexdigest()

    client = boto3.client('dynamodb')

    try:
        response: dict = client.put_item(
            TableName=os.environ['DYNAMODB_TABLE_NAME'],
            Item={
                'id': {
                    'S': article_id,
                },
                'publish-timestamp': {
                    'N': str(publish_timestamp),
                },
                'publisher-email': {
                    'S': article['publisher-email'],
                },
                'publisher-name': {
                    'S': article['publisher-name'],
                },
                'item-type': {
                    'S': 'blog-article',
                },
                'title': {
                    'S': article['title'],
                },
                'body': {
                    'S': article['body'],
                },
                'likes': {
                    'N': str(0),
                },
                # The article will be auto-deleted by Dynamo after certain time
                TIME_TO_LIVE_ATTR_NAME: {
                    'N': str(publish_timestamp + TIME_TO_LIVE_DURATION),
                },
            },
            # Make sure we don't override a previously entered article
            ConditionExpression='attribute_not_exists(#id)',
            ExpressionAttributeNames={
                '#id': 'id',
            },
        )

    except botocore.exceptions.ClientError as err:
        if err.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise CustomException(ErrorMsg.ARTICLE_ALREADY_EXISTS) from err
        else:
            raise err

    print('DYNAMODB PUT ITEM RESPONSE:')
    print(json.dumps(response))

    status: int = response.get('ResponseMetadata', {}).get('HTTPStatusCode')

    public_message: str = 'Article published' if status == 200 else \
        'Error! Could not save the article'

    return {
        'status_code': status,
        'public_message': public_message,
        'public_data': {
            'article': {
                'id': article_id,
                'publish-datetime': date_str(publish_timestamp),
                'publisher-email': article['publisher-email'],
                'publisher-name': article['publisher-name'],
                'title': article['title'],
                'body': article['body'],
                'likes': 0,
            },
        },
    }


def like_article(*, event):
    try:
        article_id: Dict[str, str] = json.loads(event['body'])['article_id']
    except Exception as error:
        raise CustomException(ErrorMsg.UNAVAILABLE_ARTICLE_ID) from error

    client = boto3.client('dynamodb')

    try:
        response = client.update_item(
            TableName=os.environ['DYNAMODB_TABLE_NAME'],
            Key={
                'id': {
                    'S': article_id,
                },
            },
            UpdateExpression='SET #likes = #likes + :incr',
            ConditionExpression='attribute_exists(#likes)',
            ExpressionAttributeNames={
                '#likes': 'likes',
            },
            ExpressionAttributeValues={
                ':incr': {
                    'N': '1',
                },
            },
            ReturnValues='UPDATED_NEW',
        )

        return {
            'public_message': 'Article liked',
            'public_data': {
                'new_likes_count': int(response['Attributes']['likes']['N']),
            },
        }

    except botocore.exceptions.ClientError as err:
        if err.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise CustomException(ErrorMsg.ARTICLE_DOES_NOT_EXIST) from err
        else:
            raise err

    except Exception as error:
        logger.exception(error)

        return {
            'public_message': 'Sorry, the like could not be processed',
        }


if __name__ == '__main__':
    event = {
        'httpMethod': 'OPTIONS',
    }

    response = handler(event=event, context=None)
