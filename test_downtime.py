import datetime

import pytest
import downtime


downtime.START_TIME = datetime.time(22, 30)
downtime.END_TIME = datetime.time(6, 30)

def test_is_before_downtime():
    now = datetime.time(17, 49)
    assert not downtime.is_downtime(now)
    
def test_is_after_downtime():
    now = datetime.time(7, 00)
    assert not downtime.is_downtime(now)

def test_is_in_downtime():
    now = datetime.time(23, 57)
    assert downtime.is_downtime(now)

def test_is_in_downtime_nextday():
    now = datetime.time(3, 30)
    assert downtime.is_downtime(now)

def test_tight_interval():
    now = datetime.time(18, 50)
    downtime.START_TIME = datetime.time(18, 30) # 6:30pm
    downtime.END_TIME = datetime.time(18, 45) # 6:45pm
    assert not downtime.is_downtime(now)
