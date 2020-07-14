#! /usr/bin/python3.8 Python3.8
from unittest import mock


@mock.patch('streams_reader.put_firehose')
def test_full(patch_put_firehose, sample_ddb_streams):
    from streams_reader import handler

    patch_put_firehose.return_value = {'patch': 'put_firehose'}

    handler(event=sample_ddb_streams, context=None)

    print(patch_put_firehose.mock_calls)

    assert patch_put_firehose.call_count == 2
