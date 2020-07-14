#! /usr/bin/python3.8 Python3.8
from typing import Union


class ErrorMsg:

    GENERIC_PUBLIC_ERROR = 'Sorry, there was an error'

    NOT_DDB_STREAM = 'Record is not a DynamoDB Stream'

    UNDEFINED_PARSER = 'Parser is not defined for Record'

    PARSE_ERROR_INSERT = 'Failed to parse an "INSERT" event'

    PARSE_ERROR_MODIFY = 'Failed to parse a "MODIFY" event'


class CustomException(Exception):

    def __init__(
            self,
            public_message: Union[str, None],
            *args,
            **kwargs,
    ) -> None:
        if type(public_message) not in [str, None]:
            raise TypeError(ErrorMsg.PUBLIC_MSG_TYPE_ERROR)

        self.public_message: str = public_message

    def __str__(self):
        return f'{self.public_message}'
