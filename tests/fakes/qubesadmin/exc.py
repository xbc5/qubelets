class QubesException(Exception):
    pass


class QubesVMNotFoundError(QubesException, KeyError):
    pass
