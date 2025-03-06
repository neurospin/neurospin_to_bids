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
        return doc[:LINE_LENGTH] + '\n' + ' ' * pos + '^ ' + json_decode_error.msg
    else:
        return (
            '...'
            + doc[start : (start + LINE_LENGTH - len('...'))]
            + '\n'
            + ' ' * (pos - start)
            + '^ '
            + json_decode_error.msg
        )


NONINTERACTIVE = False


def set_noninteractive(noninteractive=True):
    """Set the noninteractive flag globally for the current process."""
    global NONINTERACTIVE
    NONINTERACTIVE = noninteractive


def yes_no(question: str, *, default=None, noninteractive=None) -> bool:
    """A simple yes/no prompt

    Args:
        question (str): The question to be answered.
        default (optional): Default answer to `question`, selected if the user
                            just hits the Enter key. Must be one of 'yes',
                            'no', or None. Defaults to None, which means that
                            there is no default answer, the user must type
                            either yes or no before hitting Enter.
        noninteractive (optional): value returned in non-interactive mode, must
                                   be one of True or False. The default value
                                   is None, which means that the returned value
                                   is given by the 'default' argument.

    Raises:
        ValueError: Raise `ValueError` when default answer is not
                    `yes` or `no`.

    Returns:
        bool: Boolean answer to the yes/no question.
    """
    valid = {'yes': True, 'y': True, 'no': False, 'n': False}
    if NONINTERACTIVE:
        if noninteractive is not None:
            return noninteractive
        else:
            try:
                return valid[default]
            except KeyError:
                raise ValueError(
                    'Missing or invalid default value, cannot '
                    'use noninteractive mode. You should use the '
                    "'default' or 'noninteractive' argument."
                )
    if default is None:
        prompt = ' [y/n] '
    elif default == 'yes':
        prompt = ' [Y/n] '
    elif default == 'no':
        prompt = ' [y/N] '
    else:
        raise ValueError(f"invalid default answer: '{default}'")

    while True:
        choice = input(question + prompt).lower()
        if choice == '' and default is not None:
            return valid[default]
        if choice in valid:
            return valid[choice]
        print("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")
