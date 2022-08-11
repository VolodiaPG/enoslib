# -*- coding: utf-8 -*-


class EnosError(Exception):
    pass


class InvalidReservationTime(EnosError):
    def __init__(self, time):
        self.time = time


class InvalidReservationTooOld(EnosError):
    def __init__(self):
        self.msg = "Reservation time too old"


class InvalidReservationCritical(EnosError):
    def __init__(self, msg):
        self.msg = msg


class NoSlotError(EnosError):
    def __init__(self):
        self.msg = "No slot found"


class NegativeWalltime(EnosError):
    def __init__(self):
        self.msg = "Walltime is negative"


class EnosFailedHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts


class EnosUnreachableHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts


class EnosSSHNotReady(EnosError):
    def __init__(self, msg):
        super(EnosSSHNotReady, self).__init__(msg)


class EnosFilePathError(EnosError):
    def __init__(self, filepath, msg=""):
        super(EnosFilePathError, self).__init__(msg)
        self.filepath = filepath


# NOTE(msimonin): vital organs extraction doesn't use it currently
class EnosProviderMissingConfigurationKeys(EnosError):
    def __init__(self, missing_overridden):
        super(EnosProviderMissingConfigurationKeys, self).__init__(
            "Keys %s have to be overridden in the provider "
            "section of the reservation file." % missing_overridden
        )
        self.missing_ovorridden = missing_overridden
