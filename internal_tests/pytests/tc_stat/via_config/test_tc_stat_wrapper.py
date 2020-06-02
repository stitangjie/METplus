#!/usr/bin/env python

import os
import sys
import pytest

import produtil

from metplus.util import config_metplus
from metplus.wrappers.tc_stat_wrapper import TCStatWrapper

#
# -----------Mandatory-----------
#  configuration and fixture to support METplus configuration files beyond
#  the metplus_data, metplus_system, and metplus_runtime conf files.
#


# Add a test configuration
def pytest_addoption(parser):
    """! For supporting config files from the command line"""
    parser.addoption("-c", action="store", help=" -c <test config file>")


# @pytest.fixture
def cmdopt(request):
    """! For supporting the additional config files used by METplus"""
    return request.config.getoption("-c")


#
# ------------Pytest fixtures that can be used for all tests ---------------
#
@pytest.fixture
def tc_stat_wrapper():
    """! Returns a default TCStatWrapper with /path/to entries in the
         metplus_system.conf and metplus_runtime.conf configuration
         files.  Subsequent tests can customize the final METplus configuration
         to over-ride these /path/to values."""

    # Default, empty TCStatWrapper with some configuration values set
    # to /path/to:
    conf = metplus_config()
    return TCStatWrapper(conf, None)



@pytest.fixture
def metplus_config():
    """! Generate the METplus config object"""
    try:
        if 'JLOGFILE' in os.environ:
            produtil.setup.setup(send_dbn=False, jobname='TCStatWrapper ',
                                 jlogfile=os.environ['JLOGFILE'])
        else:
            produtil.setup.setup(send_dbn=False, jobname='TCStatWrapper ')
        produtil.log.postmsg('tc_stat_wrapper  is starting')

        # Read in the configuration object CONFIG
        config = config_metplus.setup()
        return config

    except Exception as e:
        produtil.log.jlogger.critical(
            'tc_stat_wrapper failed: %s' % (str(e),), exc_info=True)
        sys.exit(2)


@pytest.mark.parametrize(
    'key, value', [
        ('APP_PATH', '/usr/local/met-8.0/bin/tc_stat'),
        ('APP_NAME', 'tc_stat'),
        ('INIT_BEG', '20170705'),
        ('INIT_END', '20170901'),
        ('INIT_HOUR', ['00'])
    ]
)
def test_tc_stat_dict(key, value):
    """! Test that the expected values set in the tc_stat_filter.conf
         file are correctly read/captured in the tc_stat_dict dictionary
    """
    tcsw = tc_stat_wrapper()
    actual_value = tcsw.tc_stat_dict[key]
    assert actual_value == value


def test_config_lists():
    """! Test that when the COLUMN_THRESH_NAME and COLUMN_THRESH_VAL lists
         are of different length, the appropriate value is returned
         from config_lists_ok()
    """
    tcsw = tc_stat_wrapper()

    # Uneven lengths, expect False to be returned
    column_thresh_name = "A, B, C"
    column_thresh_val = "1,2"
    tcsw.tc_stat_dict['COLUMN_THRESH_NAME'] = column_thresh_name
    tcsw.tc_stat_dict['COLUMN_THRESH_VAL'] = column_thresh_val
    assert tcsw.config_lists_ok() is False


def test_filter_by_al_basin():
    """! Test that for a given time window of SBU GFS data, the expected number
         of results is returned when additional filtering by basin=["AL"].
    """

    tcsw = tc_stat_wrapper()
    tcsw.tc_stat_dict['INIT_BEG'] = "20170705"
    tcsw.tc_stat_dict['INIT_END'] = "20170901"
    tcsw.tc_stat_dict['BASIN'] = ["AL"]
    # expect only 13 lines of output (including the header) for SBU data
    expected_num_lines = 13
    tcsw.run_all_times()
    output_file = \
        tcsw.tc_stat_dict['OUTPUT_BASE'] + "/tc_stat/tc_stat_summary.tcst"
    with open(output_file, 'r') as out_file:
        lines = len(out_file.readlines())
        print("Num lines: ", str(lines))

    assert lines == expected_num_lines


def test_filter_by_cyclone():
    """! Test that for a given time window of SBU GFS data, the expected number
         of results is returned when additional filtering by cyclone.
    """

    tcsw = tc_stat_wrapper()
    tcsw.tc_stat_dict['INIT_BEG'] = "20170705"
    tcsw.tc_stat_dict['INIT_END'] = "20170901"
    tcsw.tc_stat_dict['CYCLONE'] = ["10"]

    # expect only 13 lines of output (including the header) for SBU data
    expected_num_lines = 13
    tcsw.run_all_times()
    output_file = \
        tcsw.tc_stat_dict['OUTPUT_BASE'] + "/tc_stat/tc_stat_summary.tcst"
    with open(output_file, 'r') as out_file:
        lines = len(out_file.readlines())
        # print("Num lines: ", str(lines))

    assert lines == expected_num_lines


def test_filter_by_storm_name():
    """! Test that for a given time window of SBU GFS data, the expected number
         of results is returned when additional filtering by storm_name.
    """

    tcsw = tc_stat_wrapper()
    tcsw.tc_stat_dict['INIT_BEG'] = "20170705"
    tcsw.tc_stat_dict['INIT_END'] = "20170901"
    tcsw.tc_stat_dict['STORM_NAME'] = ["TEN"]
    # expect only 13 lines of output (including the header) for SBU data
    expected_num_lines = 13
    tcsw.run_all_times()
    output_file = \
        tcsw.tc_stat_dict['OUTPUT_BASE'] + "/tc_stat/tc_stat_summary.tcst"
    with open(output_file, 'r') as out_file:
        lines = len(out_file.readlines())
        print("Num lines: ", str(lines))

    assert lines == expected_num_lines


def test_filter_by_storm_id():
    """! Test that for a given time window of SBU GFS data, the expected number
         of results is returned when additional filtering by storm_id.  For
         this data and the indicated storm_id, tc_stat does not return any
         data
    """

    tcsw = tc_stat_wrapper()
    tcsw.tc_stat_dict['INIT_BEG'] = "20170105"
    tcsw.tc_stat_dict['INIT_END'] = "20170901"
    tcsw.tc_stat_dict['STORM_ID'] = ["AL102017"]
    # expect only 13 lines of output (including the header) for SBU data
    expected_num_lines = 13
    tcsw.run_all_times()
    output_file = \
        tcsw.tc_stat_dict['OUTPUT_BASE'] + "/tc_stat/tc_stat_summary.tcst"
    with open(output_file, 'r') as out_file:
        lines = len(out_file.readlines())
        print("Num lines: ", str(lines))

    assert lines == expected_num_lines


def test_filter_by_basin_cyclone():
    """! Test that for a given time window of SBU GFS data, the expected number
         of results is returned when additional filtering by basin and cyclone
         to get the same results as if filtering by storm_id (which doesn't
         work, perhaps because the storm_id is greater than 2-digits?).
    """

    tcsw = tc_stat_wrapper()
    tcsw.tc_stat_dict['INIT_BEG'] = "20170705"
    tcsw.tc_stat_dict['INIT_END'] = "20170901"
    tcsw.tc_stat_dict['CYCLONE'] = ["10"]
    tcsw.tc_stat_dict['BASIN'] = ["AL"]

    # expect only 13 lines of output (including the header) for SBU data
    expected_num_lines = 13
    tcsw.run_all_times()
    output_file = \
        tcsw.tc_stat_dict['OUTPUT_BASE'] + "/tc_stat/tc_stat_summary.tcst"
    with open(output_file, 'r') as out_file:
        lines = len(out_file.readlines())
        print("Num lines: ", str(lines))

    assert lines == expected_num_lines

#



