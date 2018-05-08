#!/usr/bin/env python

from __future__ import print_function

import pytest
from string_template_substitution import StringSub
import logging


def test_cycle_hour():
    cycle_string = "00"
    valid_string = "20180103"
    logger = logging.getLogger("dummy")
    templ = "prefix.{valid?fmt=%Y%m%d}.tm{cycle?fmt=%H}"
    ss = StringSub(logger, templ, valid=valid_string, cycle=cycle_string)
    expected_hours = int(0)
    assert (ss.cycle_time_hours == expected_hours)


def test_offset_hour():
    logger = logging.getLogger("dummy")
    expected_hour = int(3)
    offset = "03"
    templ = "prefix.{valid?fmt=%Y%m%d}.tm{offset?fmt=%H}"
    ss = StringSub(logger, templ, offset=offset)
    assert (ss.offset_hour == expected_hour)


@pytest.mark.parametrize(
    'key, value', [
        ('00', '20180103060000'),
        ('03', '20180103030000'),
        ('06', '20180103000000'),
        ('72', '20171231060000')
    ]
)
def test_calc_valid_for_prepbufr(key, value):
    # Verify that the previous day is correctly calculated when
    # the negative_offset_hour > cycle_hour
    cycle_hour = "00"
    init_string = "2018010306"
    logger = logging.getLogger("dummy")
    templ = "prefix.{valid?fmt=%Y%m%d%H}.tm{cycle?fmt=%H}z.tm{" \
        "offset?fmt=%H}.nc"

    ss = StringSub(logger, templ, init=init_string, cycle=cycle_hour,
               offset=key)
    valid_time = ss.calc_valid_for_prepbufr()
    assert (valid_time == value)


def test_gdas_substitution():
    # Test that the string template substitution works correctly for GDAS
    # prepbufr files, which do not make use of the cycle hour or the offset
    # to generate the valid time.
    valid_string = "2018010411"
    logger = logging.getLogger("testing")
    templ = "prepbufr.gdas.{valid?fmt=%Y%m%d%H}.nc"
    expected_filename = 'prepbufr.gdas.' + valid_string + '.nc'
    ss = StringSub(logger, templ, valid=valid_string)
    filename = ss.doStringSub()
    # print("expected filename ", expected_filename, " gdas filename: ", filename)
    assert(filename == expected_filename)

@pytest.mark.parametrize(
    'key, value', [
        ('38', 'prepbufr.nam.2018010311.t38z.tm03.nc'),
        ('380', 'prepbufr.nam.2018011717.t380z.tm03.nc')

    ]
)
def test_nam_substitution_HH(key, value):
    # Test that the substitution works correctly when given an init time,
    # cycle hour, and negative offset hour.
    init_string = "20180102"
    cycle_string = key
    offset_string = '03'
    expected_filename = value
    logger = logging.getLogger("test")
    templ = \
        'prepbufr.nam.{valid?fmt=%Y%m%d%H}.t{cycle?fmt=%HH}z.tm{' \
        'offset?fmt=%HH}.nc'
    ss = StringSub(logger, templ, init=init_string, cycle=cycle_string,
                   offset=offset_string)
    filename = ss.doStringSub()
    # print('nam filename: ', filename)
    assert (filename == expected_filename)


@pytest.mark.parametrize(
    'key, value', [
        ('18', 'prepbufr.nam.2018010215.t018z.tm03.nc'),
        ('03', 'prepbufr.nam.2018010200.t003z.tm03.nc'),

    ]
)
def test_nam_substitution_HHH(key, value):
    # Test that the substitution works correctly when given an init time,
    # cycle hour, and negative offset hour.
    init_string = "20180102"
    cycle_string = key
    offset_string = '03'
    expected_filename = value
    logger = logging.getLogger("test")
    templ = \
        'prepbufr.nam.{valid?fmt=%Y%m%d%H}.t{cycle?fmt=%HHH}z.tm{' \
        'offset?fmt=%HH}.nc'
    ss = StringSub(logger, templ, init=init_string, cycle=cycle_string,
                   offset=offset_string)
    filename = ss.doStringSub()
    # print('nam filename: ', filename)
    assert (filename == expected_filename)


@pytest.mark.parametrize(
    'key, value', [
        ('38', 'prepbufr.nam.2018010311.t01_13_59_59z.tm03.nc'),
        ('380', 'prepbufr.nam.2018011717.t15_20_00_00z.tm03.nc')
    ]
)
def test_nam_substitution_dHMS(key, value):
        # Test that the substitution works correctly when given an init time,
        # cycle hour, and negative offset hour.
        init_string = "20180102"
        cycle_string = key
        offset_string = '03'
        expected_filename = value
        logger = logging.getLogger("test")
        templ = \
            'prepbufr.nam.{valid?fmt=%Y%m%d%H}.t{cycle?fmt=%dd%HH%M%S}z.tm{' \
            'offset?fmt=%HH}.nc'
        ss = StringSub(logger, templ, init=init_string, cycle=cycle_string,
                       offset=offset_string)
        filename = ss.doStringSub()
        # print('nam filename: ', filename)
        assert (filename == expected_filename)


def test_ym_date_dir_init():
    # Test that the ym directory can be read in and does substitution correctly
    logger = logging.getLogger("test")
    # e.g. /d1/METplus_TC/adeck_orig/201708/atcfunix.gfs.2017080100
    init_str = '2017080100'
    date_str = '201708'
    templ = '/d1/METplus_TC/adeck_orig/{date?fmt=%s}/atcfunix.gfs.{init?fmt=%Y%m%d%H}.dat'
    ss = StringSub(logger, templ, date=date_str, init=init_str)
    filename = ss.doStringSub()
    expected_filename = '/d1/METplus_TC/adeck_orig/201708/atcfunix.gfs.2017080100.dat'
    assert filename == expected_filename


def test_ym_date_dir():
    # Test that the ym directory can be read in and does substitution correctly
    logger = logging.getLogger("test")
    # e.g. /d1/METplus_TC/adeck_orig/201708/atcfunix.gfs.2017080100
    date_str = '201708'
    templ = '/d1/METplus_TC/adeck_orig/{date?fmt=%s}/atcfunix.gfs.2017080100.dat'
    ss = StringSub(logger, templ, date=date_str)
    filename = ss.doStringSub()
    expected_filename = '/d1/METplus_TC/adeck_orig/201708/atcfunix.gfs.2017080100.dat'
    assert filename == expected_filename
# 
def test_ymd_date_dir():
    # Test that the ymd directory can be read in and does substitution correctly
    logger = logging.getLogger("test")
    # e.g. /d1/METplus_TC/adeck_orig/20170811/atcfunix.gfs.2017080100
    init_str = '2017081118'
    date_str = '20170811'
    templ = '/d1/METplus_TC/adeck_orig/{date?fmt=%s}/atcfunix.gfs.{init?fmt=%Y%m%d%H}.dat'
    ss = StringSub(logger, templ, date=date_str, init=init_str)
    filename = ss.doStringSub()
    expected_filename = '/d1/METplus_TC/adeck_orig/20170811/atcfunix.gfs.2017081118.dat'
    assert filename == expected_filename
# 
def test_ymd_region_cyclone():
    # Test that we can recreate the full file path with a date, region, and cyclone
    logger = logging.getLogger("test")
    # /d1/METplus_TC/bdeck_orig/20170811/bal052017.dat
    date_str = '201708'
    region_str = 'al'
    cyclone_str = '05'
    year_str = '2017'
    # templ = '/d1/METplus_TC/bdeck/{date?fmt=%Y%m}/bal{region?fmt=%s}.dat'
    templ = '/d1/METplus_TC/bdeck/{date?fmt=%s}/b{region?fmt=%s}{cyclone?fmt=%s}{misc?fmt=%s}.dat'
    ss = StringSub(logger, templ, date=date_str, region=region_str, cyclone=cyclone_str, misc=year_str)
    full_file = ss.doStringSub()
    expected_full_file = '/d1/METplus_TC/bdeck/201708/bal052017.dat'
    assert full_file == expected_full_file
