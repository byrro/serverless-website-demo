#! /usr/bin/python3.8 Python3.8
from typing import Optional, Union


class ErrorMsg:

    GENERIC_PUBLIC_ERROR = 'Sorry, there was an error'

    STORE_HTTP_REQUEST_INFO = 'Failed to store HTTP request information'

    STATUS_CODE_TYPE_ERROR = "CustomException status_code must be an integer"

    PUBLIC_MSG_TYPE_ERROR = 'CustomException public_message must be a str'

    MISSING_ACTION_PARAM = 'Missing query string "action"'

    INVALID_ACTION = "Unrecognized action '{}'"

    ARTICLE_ALREADY_EXISTS = 'Another identical article is already published'

    ARTICLE_DOES_NOT_EXIST = 'Article not found'

    UNAVAILABLE_ARTICLE_DATA = 'Article data is unavailable in the request'

    UNAVAILABLE_ARTICLE_ID = 'Article ID is unavailable in the request'


class CustomException(Exception):

    def __init__(
            self,
            public_message: Union[str, None],
            status_code: Optional[int] = 400,
            *args,
            **kwargs,
            ) -> None:
        if type(status_code) is not int:
            raise TypeError(ErrorMsg.STATUS_CODE_TYPE_ERROR)

        if type(public_message) is not str:
            raise TypeError(
                f'{ErrorMsg.PUBLIC_MSG_TYPE_ERROR} > received '
                f'{type(public_message).__name__}'
            )

        self.status_code: int = status_code
        self.public_message: str = public_message

    def __str__(self):
        return f'statusCode {self.status_code}: {self.public_message}'
