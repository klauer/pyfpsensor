import ctypes
from ctypes import (c_int, POINTER, c_uint, CFUNCTYPE, c_void_p, c_double,
                    c_char_p)


fps_lib = ctypes.cdll.LoadLibrary('libfps3010.so')

bln32 = c_int  # fps3010.h: 40
IfNone = 0  # fps3010.h: 66
IfUsb = 1  # fps3010.h: 66
IfTcp = 2  # fps3010.h: 66
IfAll = 3  # fps3010.h: 66

InterfaceType = c_int  # fps3010.h: 66

# fps3010.h: 95
PositionCallback = CFUNCTYPE(c_void_p, c_uint, c_uint, c_uint,
                             POINTER(c_double) * 3)

# fps3010.h: 115
discover = fps_lib.FPS_discover
discover.argtypes = [InterfaceType, POINTER(c_uint)]
discover.restype = c_int


# fps3010.h: 133
get_device_info = fps_lib.FPS_getDeviceInfo
get_device_info.argtypes = [c_uint, POINTER(c_int), c_char_p, POINTER(bln32)]
get_device_info.restype = c_int


# fps3010.h: 146
connect = fps_lib.FPS_connect
connect.argtypes = [c_uint]
connect.restype = c_int


# fps3010.h: 155
disconnect = fps_lib.FPS_disconnect
disconnect.argtypes = [c_uint]
disconnect.restype = c_int


# fps3010.h: 166
get_position = fps_lib.FPS_getPosition
get_position.argtypes = [c_uint, c_uint, POINTER(c_double)]
get_position.restype = c_int


# fps3010.h: 178
get_positions = fps_lib.FPS_getPositions
get_positions.argtypes = [c_uint, POINTER(c_double)]
get_positions.restype = c_int


# fps3010.h: 194
set_position_callback = fps_lib.FPS_setPositionCallback
set_position_callback.argtypes = [c_uint, c_uint, PositionCallback]
set_position_callback.restype = c_int


# fps3010.h: 49
FPS_Ok = 0
FPS_Error = -1
FPS_Timeout = 1
FPS_NotConnected = 2
FPS_DriverError = 3
FPS_DeviceLocked = 7
FPS_Unknown = 8
FPS_NoDevice = 9
