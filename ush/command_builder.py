#!/usr/bin/env python

"""
Program Name: CommandBuilder.py
Contact(s): George McCabe
Abstract:
History Log:  Initial version
Usage: Create a subclass
Parameters: None
Input Files: N/A
Output Files: N/A
"""

import os
import glob
from datetime import datetime
from abc import ABCMeta
from inspect import getframeinfo, stack

from command_runner import CommandRunner
import met_util as util
import string_template_substitution as sts

# pylint:disable=pointless-string-statement
'''!@namespace CommandBuilder
@brief Common functionality to wrap all MET applications
Call as follows:
@code{.sh}
Cannot be called directly. Must use child classes.
@endcode
'''


class CommandBuilder:
    """!Common functionality to wrap all MET applications
    """
    __metaclass__ = ABCMeta

    def __init__(self, config, logger):
        self.isOK = True
        self.errors = 0
        self.logger = logger
        self.config = config
        self.env_list = set()
        self.debug = False
        self.args = []
        self.input_dir = ""
        self.infiles = []
        self.outdir = ""
        self.outfile = ""
        self.param = ""
        self.env = os.environ.copy()
        if hasattr(config, 'env'):
            self.env = config.env
        self.c_dict = self.create_c_dict()
        self.check_for_externals()

        self.cmdrunner = CommandRunner(self.config, logger=self.logger,
                                       verbose=self.c_dict['VERBOSITY'])

        # if env MET_TMP_DIR was not set, set it to config TMP_DIR
        if 'MET_TMP_DIR' not in self.env:
            self.add_env_var('MET_TMP_DIR', self.config.getdir('TMP_DIR'))

        self.clear()

    def create_c_dict(self):
        c_dict = dict()
        # set skip if output exists to False for all wrappers
        # wrappers that support this functionality can override this value
        c_dict['VERBOSITY'] = self.config.getstr('config', 'LOG_MET_VERBOSITY', '2')
        c_dict['SKIP_IF_OUTPUT_EXISTS'] = False
        c_dict['FCST_INPUT_DATATYPE'] = ''
        c_dict['OBS_INPUT_DATATYPE'] = ''
        c_dict['ALLOW_MULTIPLE_FILES'] = False
        c_dict['CURRENT_VAR_INFO'] = None

        c_dict['CUSTOM_LOOP_LIST'] = util.get_custom_string_list(self.config,
                                                                 self.app_name)


        return c_dict

    def clear(self):
        """!Unset class variables to prepare for next run time
        """
        self.args = []
        self.input_dir = ""
        self.infiles = []
        self.outdir = ""
        self.outfile = ""
        self.param = ""
        self.env_list.clear()

        # add MET_TMP_DIR back to env_list
        self.add_env_var('MET_TMP_DIR', self.config.getdir('TMP_DIR'))

    def log_error(self, error_string):
        caller = getframeinfo(stack()[1][0])
        self.logger.error(f"({os.path.basename(caller.filename)}:{caller.lineno}) {error_string}")
        self.errors += 1

    def set_user_environment(self, time_info=None):
        """!Set environment variables defined in [user_env_vars] section of config
        """
        if time_info is None:
            time_info = {'now': datetime.strptime(self.config.getstr('config', 'CLOCK_TIME'),
                                                  '%Y%m%d%H%M%S')}

        if 'user_env_vars' not in self.config.sections():
            self.config.add_section('user_env_vars')

        for env_var in self.config.keys('user_env_vars'):
            # perform string substitution on each variable
            raw_env_var_value = self.config.getraw('user_env_vars', env_var)
            env_var_value = sts.StringSub(self.logger,
                                          raw_env_var_value,
                                          **time_info).do_string_sub()
            self.add_env_var(env_var, env_var_value)

    def add_common_envs(self, time_info=None):
        # Set the environment variables
        self.add_env_var('MODEL', str(self.c_dict['MODEL']))

        to_grid = self.c_dict['REGRID_TO_GRID'].strip('"')
        if not to_grid:
            to_grid = 'NONE'

        # if not surrounded by quotes and not NONE, FCST or OBS, add quotes
        if to_grid not in ['NONE', 'FCST', 'OBS']:
            to_grid = f'"{to_grid}"'

        self.add_env_var('REGRID_TO_GRID', to_grid)

        # set user environment variables
        self.set_user_environment(time_info)

    def print_all_envs(self):
        # send environment variables to logger
        self.logger.debug("ENVIRONMENT FOR NEXT COMMAND: ")
        for env_item in sorted(self.env_list):
            self.print_env_item(env_item)

        self.logger.debug("COPYABLE ENVIRONMENT FOR NEXT COMMAND: ")
        self.print_env_copy()

    def handle_window_once(self, c_dict, dtype, edge, app_name):
        """! Check and set window dictionary variables like
              OBS_WINDOW_BEG or FCST_FILE_WINDW_END
              Args:
                @param c_dict dictionary to set items in
                @param dtype type of data 'FCST' or 'OBS'
                @param edge either 'BEGIN' or 'END'
        """
        app = app_name.upper()

        # if value specific to given wrapper is set, override value
        if self.config.has_option('config',
                                  dtype + '_' + app + '_WINDOW_' + edge):
            c_dict[dtype + '_WINDOW_' + edge] = \
                self.config.getseconds('config',
                                   dtype + '_' + app + '_WINDOW_' + edge)
        # if generic value is set, use that
        elif self.config.has_option('config',
                                    dtype + '_WINDOW_' + edge):
            c_dict[dtype + '_WINDOW_' + edge] = \
                self.config.getseconds('config',
                                       dtype + '_WINDOW_' + edge)
        # otherwise set to default of 0
        else:
            c_dict[dtype + '_WINDOW_' + edge] = 0

        # do the same for FILE_WINDOW
        if self.config.has_option('config',
                                  dtype + '_' + app + '_FILE_WINDOW_' + edge):
            c_dict[dtype + '_FILE_WINDOW_' + edge] = \
                self.config.getseconds('config',
                                   dtype + '_' + app + '_FILE_WINDOW_' + edge)
        elif self.config.has_option('config',
                                    dtype + '_FILE_WINDOW_' + edge):
            c_dict[dtype + '_FILE_WINDOW_' + edge] = \
                self.config.getseconds('config',
                                       dtype + '_FILE_WINDOW_' + edge)
        # otherwise set to 0
        else:
            c_dict[dtype + '_FILE_WINDOW_' + edge] = 0

    def handle_window_variables(self, c_dict, app_name, dtypes=['FCST', 'OBS']):
        """! Handle all window config variables like
              [FCST/OBS]_<app_name>_WINDOW_[BEGIN/END] and
              [FCST/OBS]_<app_name>_FILE_WINDOW_[BEGIN/END]
              Args:
                @param c_dict dictionary to set items in
        """
        edges = ['BEGIN', 'END']

        for dtype in dtypes:
            for edge in edges:
                self.handle_window_once(c_dict, dtype, edge, app_name)

    def set_output_path(self, outpath):
        """!Split path into directory and filename then save both
        """
        self.outfile = os.path.basename(outpath)
        self.outdir = os.path.dirname(outpath)

    def get_output_path(self):
        """!Combine output directory and filename then return result
        """
        return os.path.join(self.outdir, self.outfile)

    def add_env_var(self, key, name):
        """!Sets an environment variable so that the MET application
        can reference it in the parameter file or the application itself
        """
        self.env[key] = name
        self.env_list.add(key)

    def print_env(self):
        """!Print all environment variables set for this application
        """
        for env_name in self.env:
            self.logger.debug(env_name + '="' + self.env[env_name] + '"')

    def print_env_copy(self, var_list=None):
        self.logger.debug(self.get_env_copy(var_list))

    def get_env_copy(self, var_list=None):
        """!Print list of environment variables that can be easily
        copied into terminal
        """
        out = ""
        if not var_list:
            var_list = self.env_list

        if 'user_env_vars' in self.config.sections():
            for user_var in self.config.keys('user_env_vars'):
                var_list.add(user_var)

        shell = self.config.getstr('config', 'USER_SHELL', 'bash').lower()
        for var in sorted(var_list):
            if shell == 'csh':
                line = 'setenv ' + var + ' "' + self.env[var].replace('"', '"\\""') + '"'
            else:
                line = 'export ' + var + '="' + self.env[var].replace('"', '\\"') + '"'

            out += line + '; '

        return out

    def print_env_item(self, item):
        """!Print single environment variable in the log file
        """
        self.logger.debug(item + "=" + self.env[item])

    def print_user_env_items(self):
        """!Prints user environment variables in the log file
        """
        for k in self.config.keys('user_env_vars') + ['MET_TMP_DIR']:
            self.print_env_item(k)

    def handle_fcst_and_obs_field(self, gen_name, fcst_name, obs_name, default=None, sec='config'):
        """!Handles config variables that have fcst/obs versions or a generic
            variable to handle both, i.e. FCST_NAME, OBS_NAME, and NAME.
            If FCST_NAME and OBS_NAME both exist, they are used. If both are don't
            exist, NAME is used.
        """
        has_gen = self.config.has_option(sec, gen_name)
        has_fcst = self.config.has_option(sec, fcst_name)
        has_obs = self.config.has_option(sec, obs_name)

        # use fcst and obs if both are set
        if has_fcst and has_obs:
            fcst_conf = self.config.getstr(sec, fcst_name)
            obs_conf = self.config.getstr(sec, obs_name)
            if has_gen:
                self.logger.warning('Ignoring conf {} and using {} and {}'
                                    .format(gen_name, fcst_name, obs_name))
            return fcst_conf, obs_conf

        # if one but not the other is set, error and exit
        if has_fcst and not has_obs:
            self.log_error('Cannot use {} without {}'.format(fcst_name, obs_name))
            return None, None

        if has_obs and not has_fcst:
            self.log_error('Cannot use {} without {}'.format(obs_name, fcst_name))
            return None, None

        # if generic conf is set, use for both
        if has_gen:
            gen_conf = self.config.getstr(sec, gen_name)
            return gen_conf, gen_conf

        # if none of the options are set, use default value for both if specified
        if default is None:
            msg = 'Must set both {} and {} in the config files'.format(fcst_name,
                                                                       obs_name)
            msg += ' or set {} instead'.format(gen_name)
            self.log_error(msg)

            return None, None

        self.logger.warning('Using default values for {}'.format(gen_name))
        return default, default

    def find_model(self, time_info, var_info, mandatory=True, return_list=False):
        """! Finds the model file to compare
              Args:
                @param time_info dictionary containing timing information
                @param var_info object containing variable information
                @param mandatory if True, report error if not found, warning if not
                  default is True
                @rtype string
                @return Returns the path to an model file
        """
        return self.find_data(time_info, var_info, "FCST",
                              mandatory=mandatory,
                              return_list=return_list)

    def find_obs(self, time_info, var_info, mandatory=True, return_list=False):
        """! Finds the observation file to compare
              Args:
                @param time_info dictionary containing timing information
                @param var_info object containing variable information
                @param mandatory if True, report error if not found, warning if not
                  default is True
                @rtype string
                @return Returns the path to an observation file
        """
        return self.find_data(time_info, var_info, "OBS",
                              mandatory=mandatory,
                              return_list=return_list)

    def find_data(self, time_info, var_info, data_type, mandatory=True, return_list=False):
        """! Finds the data file to compare
              Args:
                @param time_info dictionary containing timing information
                @param var_info object containing variable information
                @param data_type type of data to find (FCST or OBS)
                @param mandatory if True, report error if not found, warning if not
                  default is True
                @rtype string
                @return Returns the path to an observation file
        """
        if var_info is not None:
            # set level based on input data type
            if data_type.startswith("OBS"):
                v_level = var_info['obs_level']
            else:
                v_level = var_info['fcst_level']

            # separate character from beginning of numeric level value if applicable
            level = util.split_level(v_level)[1]

            # set level to 0 character if it is not a number
            if not level.isdigit():
                level = '0'
        else:
            level = '0'

        # arguments for find helper functions
        arg_dict = {'level': level,
                    'data_type': data_type,
                    'mandatory': mandatory,
                    'time_info': time_info,
                    'return_list': return_list}

        # if looking for a file with an exact time match:
        if self.c_dict[data_type + '_FILE_WINDOW_BEGIN'] == 0 and \
                self.c_dict[data_type + '_FILE_WINDOW_END'] == 0:

            return self.find_exact_file(**arg_dict)

        # if looking for a file within a time window:
        return self.find_file_in_window(**arg_dict)

    def find_exact_file(self, level, data_type, time_info, mandatory=True, return_list=False):
        input_template = self.c_dict[f'{data_type}_INPUT_TEMPLATE']
        data_dir = self.c_dict[f'{data_type}_INPUT_DIR']

        check_file_list = []
        found_file_list = []

        # check if there is a list of files provided in the template
        # process each template in the list (or single template)
        template_list = [template.strip() for template in input_template.split(',')]

        # return None if a list is provided for a wrapper that doesn't allow
        # multiple files to be processed
        if len(template_list) > 1 and not self.c_dict['ALLOW_MULTIPLE_FILES']:
            self.log_error("List of templates specified for a wrapper that "
                           "does not allow multiple files to be provided.")
            return None

        for template in template_list:
            # perform string substitution
            dsts = sts.StringSub(self.logger,
                                 template,
                                 level=(int(level.split('-')[0]) * 3600),
                                 **time_info)
            filename = dsts.do_string_sub()

            # build full path with data directory and filename
            full_path = os.path.join(data_dir, filename)

            self.logger.debug(f"Looking for {data_type} file {full_path}")

            # if wildcard expression, get all files that match
            if '?' in full_path or '*' in full_path:
                if not self.c_dict['ALLOW_MULTIPLE_FILES']:
                    self.log_error("Wildcard character found in file path when using wrapper that "
                                   "does not allow multiple files to be provided.")
                    return None

                wildcard_files = sorted(glob.glob(full_path))
                self.logger.debug(f'Wildcard file pattern: {full_path}')
                self.logger.debug(f'{str(len(wildcard_files))} files match pattern')

                # add files to list of files
                for wildcard_file in wildcard_files:
                    check_file_list.append(wildcard_file)
            else:
                # add single file to list
                check_file_list.append(full_path)

        for file_path in check_file_list:
            # check if file exists
            processed_path = util.preprocess_file(file_path,
                                                  self.c_dict[data_type + '_INPUT_DATATYPE'],
                                                  self.config)

            # report error if file path could not be found
            if not processed_path:
                msg = f"Could not find {data_type} file {file_path} using template {template}"
                if mandatory:
                    self.log_error(msg)
                else:
                    self.logger.warning(msg)

                return None

            found_file_list.append(processed_path)

        # if only one item found and return_list is False, return single item
        if len(found_file_list) == 1 and not return_list:
            return found_file_list[0]

        return found_file_list

    def find_file_in_window(self, level, data_type, time_info, mandatory=True, return_list=False):
        template = self.c_dict[f'{data_type}_INPUT_TEMPLATE']
        data_dir = self.c_dict[f'{data_type}_INPUT_DIR']

        # convert valid_time to unix time
        valid_time = time_info['valid_fmt']
        valid_seconds = int(datetime.strptime(valid_time, "%Y%m%d%H%M%S").strftime("%s"))
        # get time of each file, compare to valid time, save best within range
        closest_files = []
        closest_time = 9999999

        # get range of times that will be considered
        valid_range_lower = self.c_dict[data_type + '_FILE_WINDOW_BEGIN']
        valid_range_upper = self.c_dict[data_type + '_FILE_WINDOW_END']
        lower_limit = int(datetime.strptime(util.shift_time_seconds(valid_time, valid_range_lower),
                                            "%Y%m%d%H%M%S").strftime("%s"))
        upper_limit = int(datetime.strptime(util.shift_time_seconds(valid_time, valid_range_upper),
                                            "%Y%m%d%H%M%S").strftime("%s"))

        msg = f"Looking for {data_type} files under {data_dir} within range " +\
              f"[{valid_range_lower},{valid_range_upper}] using template {template}"
        self.logger.debug(msg)

        if not data_dir:
            self.log_error('Must set INPUT_DIR if looking for files within a time window')
            return None

        # step through all files under input directory in sorted order
        for dirpath, _, all_files in os.walk(data_dir):
            for filename in sorted(all_files):
                fullpath = os.path.join(dirpath, filename)

                # remove input data directory to get relative path
                rel_path = fullpath.replace(f'{data_dir}/', "")
                # extract time information from relative path using template
                file_time_info = util.get_time_from_file(self.logger, rel_path, template)
                if file_time_info is not None:
                    # get valid time and check if it is within the time range
                    file_valid_time = file_time_info['valid'].strftime("%Y%m%d%H%M%S")
                    # skip if could not extract valid time
                    if file_valid_time == '':
                        continue
                    file_valid_dt = datetime.strptime(file_valid_time, "%Y%m%d%H%M%S")
                    file_valid_seconds = int(file_valid_dt.strftime("%s"))
                    # skip if outside time range
                    if file_valid_seconds < lower_limit or file_valid_seconds > upper_limit:
                        continue

                    # if only 1 file is allowed, check if file is
                    # closer to desired valid time than previous match
                    if not self.c_dict['ALLOW_MULTIPLE_FILES']:
                        diff = abs(valid_seconds - file_valid_seconds)
                        if diff < closest_time:
                            closest_time = diff
                            del closest_files[:]
                            closest_files.append(fullpath)
                    # if multiple files are allowed, get all files within range
                    else:
                        closest_files.append(fullpath)

        if not closest_files:
            msg = f"Could not find {data_type} files under {data_dir} within range " +\
                  f"[{valid_range_lower},{valid_range_upper}] using template {template}"
            if mandatory:
                self.log_error(msg)
            else:
                self.logger.warning(msg)
            return None

        # check if file(s) needs to be preprocessed before returning the path
        # if one file was found and return_list if False, return single file
        if len(closest_files) == 1 and not return_list:
            return util.preprocess_file(closest_files[0],
                                        self.c_dict[data_type + '_INPUT_DATATYPE'],
                                        self.config)

        # return list if multiple files are found
        out = []
        for close_file in closest_files:
            outfile = util.preprocess_file(close_file,
                                           self.c_dict[data_type + '_INPUT_DATATYPE'],
                                           self.config)
            out.append(outfile)

        return out

    def write_list_file(self, filename, file_list):
        """! Writes a file containing a list of filenames to the staging dir"""
        list_dir = os.path.join(self.config.getdir('STAGING_DIR'), 'file_lists')
        list_path = os.path.join(list_dir, filename)

        if not os.path.exists(list_dir):
            os.makedirs(list_dir, mode=0o0775)

        self.logger.debug(f"Writing list of filenames to {list_path}")
        with open(list_path, 'w') as file_handle:
            for f_path in file_list:
                file_handle.write(f_path + '\n')
        return list_path

    def find_and_check_output_file(self, time_info):
        """!Look for expected output file. If it exists and configured to skip if it does,
            then return False"""
        outfile = sts.StringSub(self.logger,
                                self.c_dict['OUTPUT_TEMPLATE'],
                                **time_info).do_string_sub()
        outpath = os.path.join(self.c_dict['OUTPUT_DIR'], outfile)
        self.set_output_path(outpath)

        if not os.path.exists(outpath) or not self.c_dict['SKIP_IF_OUTPUT_EXISTS']:
            return True

        # if the output file exists and we are supposed to skip, don't run tool
        self.logger.debug(f'Skip writing output file {outpath} because it already '
                          'exists. Remove file or change '
                          f'{self.app_name.upper()}_SKIP_IF_OUTPUT_EXISTS to False '
                          'to process')
        return False

    def format_list_string(self, list_string):
        """!Add quotation marks around each comma separated item in the string"""
        strings = []
        for string in list_string.split(','):
            string = string.strip().replace('\'', '\"')
            if not string:
                continue
            if string[0] != '"' and string[-1] != '"':
                string = f'"{string}"'
            strings.append(string)

        return ','.join(strings)

    def check_for_externals(self):
        self.check_for_gempak()

    def check_for_gempak(self):
        # check if we are processing Gempak data
        processingGempak = False

        # if any *_DATATYPE keys in c_dict have a value of GEMPAK, we are using Gempak data
        data_types = [value for key,value in self.c_dict.items() if key.endswith('DATATYPE')]
        if 'GEMPAK' in data_types:
            processingGempak = True

        # if any filename templates end with .grd, we are using Gempak data
        template_list = [value for key,value in self.c_dict.items() if key.endswith('TEMPLATE')]

        # handle when template is a list of templates, which happens in EnsembleStat
        templates = []
        for value in template_list:
            if type(value) is list:
                 for subval in value:
                     templates.append(subval)
            else:
                templates.append(value)

        if [value for value in templates if value and value.endswith('.grd')]:
            processingGempak = True

        # If processing Gempak, make sure GempakToCF is found
        if processingGempak:
            gempaktocf_jar = self.config.getstr('exe', 'GEMPAKTOCF_JAR', '')
            self.check_gempaktocf(gempaktocf_jar)

    def check_gempaktocf(self, gempaktocf_jar):
        if not gempaktocf_jar:
            self.log_error("[exe] GEMPAKTOCF_JAR was not set if configuration file. "
                           "This is required to process Gempak data.")
            self.logger.info("Refer to the GempakToCF use case documentation for information "
                             "on how to obtain the tool: parm/use_cases/met_tool_wrapper/GempakToCF/GempakToCF.py")
            self.isOK = False
        elif not os.path.exists(gempaktocf_jar):
            self.log_error(f"GempakToCF Jar file does not exist at {gempaktocf_jar}. " +
                           "This is required to process Gempak data.")
            self.logger.info("Refer to the GempakToCF use case documentation for information "
                             "on how to obtain the tool: parm/use_cases/met_tool_wrapper/GempakToCF/GempakToCF.py")
            self.isOK = False

    def get_output_prefix(self, time_info):
        return sts.StringSub(self.logger,
                             self.config.getraw('config', f'{self.app_name.upper()}_OUTPUT_PREFIX', ''),
                             **time_info).do_string_sub()

    def check_for_python_embedding(self, input_type, var_info):
        """!Check if field name of given input type is a python script. If it is not, return the field name.
            If it is, check if the input datatype is a valid Python Embedding string, set the c_dict item
            that sets the file_type in the MET config file accordingly, and set the output string to 'python_embedding.
            Used to set up Python Embedding input for MET tools that support multiple input files, such as MTD, EnsembleStat,
            and SeriesAnalysis.
            Args:
              @param input_type type of field input, i.e. FCST, OBS, ENS, POINT_OBS, GRID_OBS, or BOTH
              @param var_info dictionary item containing field information for the current *_VAR<n>_* configs being handled
              @returns field name if not a python script, 'python_embedding' if it is, and None if configuration is invalid"""

        var_input_type = input_type.lower() if input_type != 'BOTH' else 'fcst'
        # reset file type to empty string to handle if python embedding is used for one field but not for the next
        self.c_dict[f'{input_type}_FILE_TYPE'] = ''

        if not util.is_python_script(var_info[f"{var_input_type}_name"]):
            # if not a python script, return var name
            return var_info[f"{var_input_type}_name"]

        # if it is a python script, set file extension to show that and make sure *_INPUT_DATATYPE is a valid PYTHON_* string
        file_ext = 'python_embedding'
        data_type = self.c_dict[f'{input_type}_INPUT_DATATYPE']
        if data_type not in util.PYTHON_EMBEDDING_TYPES:
            self.log_error(f"{input_type}_{self.app_name.upper()}_INPUT_DATATYPE ({data_type}) must be set to a valid Python Embedding type "
                           f"if supplying a Python script as the {input_type}_VAR<n>_NAME. Valid options: "
                           f"{','.join(util.PYTHON_EMBEDDING_TYPES)}")
            return None

        # set file type string to be set in MET config file to specify Python Embedding is being used for this dataset
        self.c_dict[f'{input_type}_FILE_TYPE'] = f"file_type = {data_type};"
        return file_ext

    def get_command(self):
        """! Builds the command to run the MET application
           @rtype string
           @return Returns a MET command with arguments that you can run
        """
        if self.app_path is None:
            self.log_error('No app path specified. '
                              'You must use a subclass')
            return None

        cmd = '{} -v {} '.format(self.app_path, self.c_dict['VERBOSITY'])

        for arg in self.args:
            cmd += arg + " "

        if not self.infiles:
            self.log_error("No input filenames specified")
            return None

        for infile in self.infiles:
            cmd += infile + " "

        if self.outfile == "":
            self.log_error("No output filename specified")
            return None

        out_path = os.path.join(self.outdir, self.outfile)

        # create outdir (including subdir in outfile) if it doesn't exist
        parent_dir = os.path.dirname(out_path)
        if parent_dir == '':
            self.log_error('Must specify path to output file')
            return None

        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        cmd += " " + out_path

        if self.param != "":
            cmd += ' ' + self.param

        return cmd

    def build_and_run_command(self):
        cmd = self.get_command()
        if cmd is None:
            self.log_error("Could not generate command")
            return
        self.build()

    # Placed running of command in its own class, command_runner run_cmd().
    # This will allow the ability to still call build() as is currenly done
    # in subclassed CommandBuilder wrappers and also allow wrappers
    # such as tc_pairs that are not heavily designed around command builder
    # to call cmdrunner.run_cmd().
    # Make sure they have SET THE self.app_name in the subclasses constructor.
    # see regrid_data_plane_wrapper.py as an example of how to set.
    def build(self):
        """!Build and run command"""
        cmd = self.get_command()
        if cmd is None:
            return False

        ret, out_cmd = self.cmdrunner.run_cmd(cmd, self.env, app_name=self.app_name,
                                              copyable_env=self.get_env_copy())
        if ret != 0:
            self.log_error(f"MET command returned a non-zero return code: {cmd}")
            self.logger.info("Check the logfile for more information on why it failed")
            return False

        return True

    # argument needed to match call
    # pylint:disable=unused-argument
    def run_at_time(self, input_dict):
        """!Used to output error and exit if wrapper is attemped to be run with
            LOOP_ORDER = times and the run_at_time method is not implemented"""
        self.log_error('run_at_time not implemented for {} wrapper. '
                          'Cannot run with LOOP_ORDER = times'.format(self.app_name))
        exit(1)

    def run_all_times(self):
        """!Loop over time range specified in conf file and
        call METplus wrapper for each time"""
        util.loop_over_times_and_call(self.config, self)
