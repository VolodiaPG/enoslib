# -*- coding: utf-8 -*-

from itertools import groupby
from enoslib.errors import NegativeWalltime
import logging


logger = logging.getLogger(__name__)


def mk_pools(things, keyfnc=lambda x: x):
    "Indexes a thing by the keyfnc to construct pools of things."
    pools = {}
    sthings = sorted(things, key=keyfnc)
    for key, thingz in groupby(sthings, key=keyfnc):
        pools.setdefault(key, []).extend(list(thingz))
    return pools


def pick_things(pools, key, n):
    "Picks a maximum of n things in a dict of indexed pool of things."
    pool = pools.get(key)
    if not pool:
        return []
    things = pool[:n]
    del pool[:n]
    return things


def offset_from_format(date_str: str, offset: int, fmt: str):
    import datetime as dt

    as_dt = dt.datetime.strptime(date_str, fmt)
    as_td = dt.timedelta(hours=as_dt.hour, minutes=as_dt.minute, seconds=as_dt.second)
    offset_as_td = dt.timedelta(seconds=offset)
    if as_td + offset_as_td < dt.timedelta(0):
        raise NegativeWalltime()
    new_as_dt = as_dt + offset_as_td
    return new_as_dt.strftime(fmt)


def _date2h(timestamp):
    # TODO(msimonin) use isoformat
    import time
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    return t