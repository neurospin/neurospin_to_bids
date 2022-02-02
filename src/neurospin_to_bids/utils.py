# -*- coding: utf-8 -*-
"""Miscellaneous utility code."""


class UserError(Exception):
    """Exception for obvious user errors that should be corrected.

    Raised if the user made an obvious error that should be corrected
    (e.g. invalid scanner name, missing required value, ).

    Contains a message describing the error.
    """
    pass


class DataError(Exception):
    """Exception for non-fatal data errors.

    Raised for conditions that prevent the import of some data (e.g. session
    not found).

    Contains a message describing the error.
    """
    pass


PREFIX_LENGTH = 20
LINE_LENGTH = 60


def pinpoint_json_error(json_decode_error):
    """Construct a user-readable message from a JSON parse error."""
    pos = json_decode_error.pos
    doc = json_decode_error.doc
    start = pos - (PREFIX_LENGTH)
    if start < 0:
        return (doc[:LINE_LENGTH]
                + '\n' + ' ' * pos + '^ ' + json_decode_error.msg)
    else:
        return ('...' + doc[start:(start+LINE_LENGTH-len('...'))]
                + '\n' + ' ' * (pos-start) + '^ ' + json_decode_error.msg)
