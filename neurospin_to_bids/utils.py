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
