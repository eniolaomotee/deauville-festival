"the errors of the festival: one fam and what went wrong"

"The command line catches FestivalError and prints the sentence. The API maps "
"each type to a status code (see API.md, Errors)"


class FestivalError(Exception):
    """Every error raised by the festival. The message is a sentence for the user."""


class NotFoundError(FestivalError):
    """Unknown artist, venue or performance (404)."""


class ConflictError(FestivalError):
    """The change clashes with what exists: busy, full, outside the days, duplicate (409)."""


class InvalidError(FestivalError):
    """A value that cannot be right: empty name, duration out of range... (422)."""


class StorageError(FestivalError):
    """The data file cannot be read or written (500)."""
