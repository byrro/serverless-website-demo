#! /usr/bin/python3.8 Python3.8
import json
from unittest import mock

import pytest

from error_handling import ErrorMsg


@mock.patch('blog.store_http_request_info')
def test_handler(patch_store_http_request_info):
    from blog import handler

    # Test a request without query string params
    try:
        response = handler(event={'hello': 'world'}, context=None)
    except Exception:
        pytest.fail(
            'Handler did not handle error gracefully '
            '(missing query string arguments in request event)'
        )

    assert type(response) is dict
    assert 'body' in response

    try:
        body = json.loads(response['body'])
    except Exception:
        pytest.fail('Could not unpack response body')

    assert 'error' in body
    assert body['error'] == ErrorMsg.MISSING_ACTION_PARAM


def test_handler_invalid_action():
    from blog import handler

    try:
        dummy_action = '!!INVALID!!'
        dummy_event = {
            'queryStringParameters': {
                'action': dummy_action,
            },
        }
        response = handler(event=dummy_event, context=None)

    except Exception:
        pytest.fail(
            'Handler did not handle error gracefully '
            '(invalid action argument in request event)'
        )

    assert type(response) is dict
    assert 'body' in response

    try:
        body = json.loads(response['body'])
    except Exception:
        pytest.fail('Could not unpack response body')

    assert 'error' in body
    assert body['error'] == ErrorMsg.INVALID_ACTION.format(dummy_action)


@mock.patch('blog.get_latest_articles')
@mock.patch('blog.put_article')
@mock.patch('blog.like_article')
def test_handler_valid_actions(
        patch_like_article,
        patch_put_article,
        patch_get_latest_articles,
        ):
    from blog import handler

    dummy_public_message = 'This is a dummy message'
    dummy_results = {
        'public_message': dummy_public_message,
    }
    patch_get_latest_articles.return_value = dummy_results
    patch_put_article.return_value = dummy_results
    patch_like_article.return_value = dummy_results

    actions = {
        'get-latest-articles': patch_get_latest_articles,
        'publish-article': patch_put_article,
        'like-article': patch_like_article,
    }

    for action, patch_executor in actions.items():
        dummy_event = {
            'queryStringParameters': {
                'action': action,
            },
        }
        response = handler(event=dummy_event, context=None)

        patch_executor.assert_called_with(event=dummy_event)

        assert type(response) is dict
        assert 'body' in response

        try:
            body = json.loads(response['body'])
        except Exception:
            pytest.fail('Could not unpack response body')

        assert type(body) is dict
        assert 'error' not in body
        assert 'message' in body
        assert 'data' in body
        assert body['message'] == dummy_public_message
        assert body['data'] is None
