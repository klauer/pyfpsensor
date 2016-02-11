import ctypes
import functools

from ctypes import (c_int, POINTER, c_uint, CFUNCTYPE, c_void_p, c_double,
                    c_char_p)


class FPSException(Exception):
    pass


def check_retval(fcn):
    '''Wrapper that checks return values from fpsensor functions

    If an error code is returned, FPSException will be raised

    Raises
    ------
    FPSException
    '''
    @functools.wraps(fcn)
    def wrapped(*args):
        ret = fcn(*args)
        if ret != Success:
            err_str = error_strings.get(ret, 'Unknown error (%d)' % ret)
            raise FPSException('Error calling %s: %s' % (fcn.__name__,
                                                         err_str))

    return wrapped


shlib = ctypes.cdll.LoadLibrary('libfps3010.so')

IfNone = 0  # fps3010.h: 66
IfUsb = 1  # fps3010.h: 66
IfTcp = 2  # fps3010.h: 66
IfAll = 3  # fps3010.h: 66

InterfaceType = c_int  # fps3010.h: 66

# fps3010.h: 95
PositionCallback = CFUNCTYPE(c_void_p, c_uint, c_uint, c_uint,
                             POINTER(c_double) * 3)

# fps3010.h: 115
discover = check_retval(shlib.FPS_discover)
discover.argtypes = [InterfaceType, POINTER(c_uint)]
discover.restype = c_int


# fps3010.h: 133
get_device_info = check_retval(shlib.FPS_getDeviceInfo)
get_device_info.argtypes = [c_uint, POINTER(c_int), c_char_p, POINTER(c_int)]
get_device_info.restype = c_int


# fps3010.h: 146
connect = check_retval(shlib.FPS_connect)
connect.argtypes = [c_uint]
connect.restype = c_int


# fps3010.h: 155
disconnect = check_retval(shlib.FPS_disconnect)
disconnect.argtypes = [c_uint]
disconnect.restype = c_int


# fps3010.h: 166
get_position = check_retval(shlib.FPS_getPosition)
get_position.argtypes = [c_uint, c_uint, POINTER(c_double)]
get_position.restype = c_int


# fps3010.h: 178
get_positions = check_retval(shlib.FPS_getPositions)
get_positions.argtypes = [c_uint, POINTER(c_double)]
get_positions.restype = c_int


# fps3010.h: 194
set_position_callback = check_retval(shlib.FPS_setPositionCallback)
set_position_callback.argtypes = [c_uint, c_uint, PositionCallback]
set_position_callback.restype = c_int


# fps3010.h: 49
Success = 0
Error = -1
Timeout = 1
NotConnected = 2
DriverError = 3
DeviceLocked = 7
Unknown = 8
NoDevice = 9


error_strings = {
    Success: "",
    Error: "Unspecified error",
    Timeout: "Communication timeout",
    NotConnected: "No active connection to device",
    DriverError: "Error in comunication with driver",
    DeviceLocked: "Device is already in use by other",
    Unknown: "Unknown error",
    NoDevice: "Invalid device number in function call",
}
