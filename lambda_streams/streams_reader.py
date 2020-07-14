#! /usr/bin/python3.8 Python3.8
import json
import logging
import queue
import os
from typing import Any, Dict, List, Optional

import boto3

from error_handling import CustomException, ErrorMsg


logger = logging.getLogger()
logger.setLevel(logging.WARNING)

FIREHOSE_ANALYTICAL_STREAM_NAME = os.environ['FIREHOSE_ANALYTICAL_STREAM_NAME']
FIREHOSE_LIKES_STREAM_NAME = os.environ['FIREHOSE_LIKES_STREAM_NAME']
FIREHOSE_APIREQUESTS_STREAM_NAME = os.environ['FIREHOSE_APIREQUESTS_STREAM_NAME']  # NOQA
FIREHOSE_QUOTA = 500

articles_queue = queue.Queue()
likes_queue = queue.Queue()
apirequests_queue = queue.Queue()


def handler(event: dict, context: Any):
    response: Dict[str, Any] = {}

    try:
        print('REQUEST EVENT:')
        print(json.dumps(event))

        parsers = {
            'INSERT': parse_new_item,
            'MODIFY': parse_item_modified,
        }

        for record in event.get('Records', []):
            if record['eventSource'] != 'aws:dynamodb':
                record_parsing_error(ErrorMsg.NOT_DDB_STREAM, record)
                continue

            parser = parsers.get(record.get('eventName'))

            if parser is None:
                record_parsing_error(ErrorMsg.UNDEFINED_PARSER, record)
                continue

            parser(record=record)

        response['results'] = process_all_queues()

    except CustomException as error:
        logger.exception(error)

        response['error']: str = error.public_message

    except Exception as error:
        logger.exception(error)

        response['error']: str = ErrorMsg.GENERIC_PUBLIC_ERROR

    finally:
        print('RESPONSE:')
        print(json.dumps(response))

        return response


def record_parsing_error(error: str, record: dict) -> None:
    logger.error(f'{error}: {json.dumps(record)}')


def parse_new_item(*, record) -> None:
    item = record['dynamodb']['NewImage']

    if item.get('item-type', {}).get('S') == 'blog-article':
        articles_queue.put({
            'id': record['dynamodb']['Keys']['id']['S'],
            'publish_timestamp': int(
                item.get('publish-timestamp', {}).get('N')
            ),
            'publisher_email': item.get('publisher-email', {}).get('S'),
            'publisher_name': item.get('publisher-name', {}).get('S'),
            'item_type': item.get('item-type', {}).get('S'),
            'title': item.get('title', {}).get('S'),
            'body': item.get('body', {}).get('S'),
        })

    if item.get('item-type', {}).get('S') == 'api-request':
        apirequests_queue.put({
            'id': record['dynamodb']['Keys']['id']['S'],
            'item_type': item.get('item-type', {}).get('S'),
            'http_method': item.get('http-method', {}).get('S'),
            'timestamp': int(item.get('timestamp', {}).get('N')),
            'datetime': item.get('datetime', {}).get('S'),
            'ip_address': item.get('ip-address', {}).get('S'),
            'user_agent': item.get('user-agent', {}).get('S'),
            'origin': item.get('origin', {}).get('S'),
            'country_code': item.get('country-code', {}).get('S'),
            'device_type': item.get('device-type', {}).get('S'),
            'action': item.get('action', {}).get('S'),
            'article_id': item.get('article-id', {}).get('S'),
        })

    # To parse new types of items, just add more conditionals here

    else:
        record_parsing_error(ErrorMsg.PARSE_ERROR_INSERT, record)


def parse_item_modified(*, record) -> None:
    if is_like(record=record):
        likes_queue.put({
            'id': record['dynamodb']['Keys']['id']['S'],
            'like': 1,
        })

    # To parse new types of modifications, just add more conditionals here

    else:
        record_parsing_error(ErrorMsg.PARSE_ERROR_MODIFY, record)


def is_like(*, record: dict) -> bool:
    old_likes = record['dynamodb']['OldImage'].get('likes', {}).get('N')
    new_likes = record['dynamodb']['NewImage'].get('likes', {}).get('N')

    return int(new_likes) > int(old_likes)


def process_all_queues():
    results: dict = {}

    queues_options = {
        'articles': {
            'queue': articles_queue,
            'firehose_stream_name': FIREHOSE_ANALYTICAL_STREAM_NAME,
        },
        'likes': {
            'queue': likes_queue,
            'firehose_stream_name': FIREHOSE_LIKES_STREAM_NAME,
        },
        'apirequests': {
            'queue': apirequests_queue,
            'firehose_stream_name': FIREHOSE_APIREQUESTS_STREAM_NAME,
        },
    }

    for data_type, options in queues_options.items():
        results[data_type]: dict = process_queue(
            queue_obj=options['queue'],
            firehose_stream_name=options['firehose_stream_name'],
        )

    return results


def process_queue(
        *,
        queue_obj: queue.Queue,
        firehose_stream_name: str,
        concurrency_limit: Optional[int] = FIREHOSE_QUOTA,
        ) -> dict:
    results: dict = {'firehose_put_records_responses': []}

    messages: list = get_msgs_from_queue(
        queue_obj=queue_obj,
        num=concurrency_limit,
    )

    while len(messages) > 0:
        response: dict = put_firehose(
            stream_name=firehose_stream_name,
            messages=messages,
        )

        results['firehose_put_records_responses'].append(response)

        messages: list = get_msgs_from_queue(
            queue_obj=queue_obj,
            num=concurrency_limit,
        )

    return results


def get_msgs_from_queue(*, queue_obj: queue.Queue, num: int) -> list:
    messages = []

    for i in range(0, num):
        try:
            messages.append(queue_obj.get(block=False))
        except queue.Empty:
            break

    return messages


def put_firehose(stream_name: str, messages: List[dict]) -> dict:
    client = boto3.client('firehose')

    records = [
        {'Data': json.dumps(msg).encode('utf-8')}
        for msg in messages
    ]

    return client.put_record_batch(
        DeliveryStreamName=stream_name,
        Records=records,
    )
