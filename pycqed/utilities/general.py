import os
# import qt
import numpy as np
import h5py
from pycqed.analysis import analysis_toolbox as a_tools
import errno

import sys
import glob
from os.path import join, dirname, exists
from os import makedirs


def get_git_revision_hash():
    import logging
    import subprocess
    try:
        # Refers to the global qc_config
        PycQEDdir = qc_config['PycQEDdir']
        hash = subprocess.check_output(['git', 'rev-parse',
                                        '--short=7', 'HEAD'], cwd=PycQEDdir)
    except:
        logging.warning('Failed to get Git revision hash, using 00000 instead')
        hash = '00000'

    return hash


def str_to_bool(s):
    valid = {'true': True, 't': True, '1': True,
             'false': False, 'f': False, '0': False, }
    if s.lower() not in valid:
        raise KeyError('{} not a valid boolean string'.format(s))
    b = valid[s.lower()]
    return b


def bool_to_int_str(b):
    if b:
        return '1'
    else:
        return '0'


def int_to_bin(x, w, lsb_last=True):
    """
    Converts an integer to a binary string of a specified width
    x (int) : input integer to be converted
    w (int) : desired width
    lsb_last (bool): if False, reverts the string e.g., int(1) = 001 -> 100
    """
    bin_str = '{0:{fill}{width}b}'.format((int(x) + 2**w) % 2**w,
                                          fill='0', width=w)
    if lsb_last:
        return bin_str
    else:
        return bin_str[::-1]


def mopen(filename, mode='w'):
    if not exists(dirname(filename)):
        try:
            makedirs(dirname(filename))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    file = open(filename, mode='w')
    return file


def dict_to_ordered_tuples(dic):
    '''Convert a dictionary to a list of tuples, sorted by key.'''
    if dic is None:
        return []
    keys = dic.keys()
    # keys.sort()
    ret = [(key, dic[key]) for key in keys]
    return ret


def to_hex_string(byteval):
    '''
    Returns a hex representation of bytes for printing purposes
    '''
    return "b'" + ''.join('\\x{:02x}'.format(x) for x in byteval) + "'"


def load_settings_onto_instrument(instrument, load_from_instr=None, folder=None,
                                  label=None,
                                  timestamp=None, **kw):
    '''
    Loads settings from an hdf5 file onto the instrument handed to the
    function.
    By default uses the last hdf5 file in the datadirectory.
    By giving a label or timestamp another file can be chosen as the
    settings file.
    '''

    older_than = None
    instrument_name = instrument.name
    success = False
    count = 0
    while success is False and count < 10:
        try:
            if folder is None:
                folder = a_tools.get_folder(timestamp=timestamp,
                                            older_than=older_than, **kw)
            else:
                folder = folder
            filepath = a_tools.measurement_filename(folder)
            f = h5py.File(filepath, 'r')
            sets_group = f['Instrument settings']
            if load_from_instr is None:
                ins_group = sets_group[instrument_name]
            else:
                ins_group = sets_group[load_from_instr]
            print('Loaded Settings Successfully')
            success = True
        except:
            older_than = os.path.split(folder)[0][-8:] \
                + '_' + os.path.split(folder)[1][:6]
            folder = None
            success = False
        count += 1

    if not success:
        print('Could not open settings for instrument "%s"' % (
            instrument_name))
        return False

    for parameter, value in ins_group.attrs.items():
        if value != 'None':  # None is saved as string in hdf5
            if type(value) == str:
                if value == 'False':
                    try:
                        instrument.set(parameter, False)
                    except:
                        print('Could not set parameter: "%s" to "%s" for instrument "%s"' % (
                            parameter, value, instrument_name))
                else:
                    try:
                        instrument.set(parameter, float(value))
                    except Exception:
                        try:
                            instrument.set(parameter, value)
                        except:
                            try:
                                instrument.set(parameter, int(value))
                            except:
                                print('Could not set parameter: "%s" to "%s" for instrument "%s"' % (
                                    parameter, value, instrument_name))
            else:
                instrument.set(parameter, value)
    f.close()
    return True


def send_email(subject='PycQED needs your attention!',
               body='', email=None):
    # Import smtplib for the actual sending function
    import smtplib
    # Here are the email package modules we'll need
    from email.mime.image import MIMEImage
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if email is None:
        email = qt.config['e-mail']

    # Create the container (outer) email message.
    msg = MIMEMultipart()
    msg['Subject'] = subject
    family = 'serwan.asaad@gmail.com'
    msg['From'] = 'Lamaserati@tudelft.nl'
    msg['To'] = email
    msg.attach(MIMEText(body, 'plain'))

    # Send the email via our own SMTP server.
    s = smtplib.SMTP_SSL('smtp.gmail.com')
    s.login('DCLabemail@gmail.com', 'DiCarloLab')
    s.sendmail(email, family, msg.as_string())
    s.quit()


def list_available_serial_ports():
    '''
    Lists serial ports

    :raises EnvironmentError:
        On unsupported or unknown platforms
    :returns:
        A list of available serial ports

    Frunction from :
    http://stackoverflow.com/questions/12090503/
        listing-available-com-ports-with-python
    '''
    import serial
    if sys.platform.startswith('win'):
        ports = ['COM' + str(i + 1) for i in range(256)]

    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this is to exclude your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')

    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')

    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def add_suffix_to_dict_keys(inputDict, suffix):
    return {str(key)+suffix: (value) for key, value in inputDict.items()}


def execfile(path, global_vars=None, local_vars=None):
    """
    Args:
        path (str)  : filepath of the file to be executed
        global_vars : use globals() to use globals from namespace
        local_vars  : use locals() to use locals from namespace

    execfile function that existed in python 2 but does not exists in python3.
    """
    with open(path, 'r') as f:
        code = compile(f.read(), path, 'exec')
        exec(code, global_vars, local_vars)


def span_lin(center, span, n):
    """
    Creates span of points around center
    Args:
        center (float) : center of the linspace
        span   (float) : span the total range of values to span
        n      (int)   : the number of points in the span

    """
    return np.linspace(center-span/2, center+span/2, n)


def span_step(center, span, stepsize):
    """
    Creates a range of points spanned around a center
    Args:
        center (float) : center of the linspace
        span   (float) : span the total range of values to span
        n      (int)   : the number of points in the span

    N.B. both boundaries are created in the span
    """
    # +.1*stepsize in the arange ensures the right boundary is included
    return np.arange(center-span/2, center+span/2+.1*stepsize, stepsize)
