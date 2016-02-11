import ctypes
from ctypes import c_int, POINTER, c_uint, CFUNCTYPE, c_void_p, c_double


fps_lib = ctypes.cdll.LoadLibrary('libfps3010.so')

bln32 = c_int  # fps3010.h: 40
IfNone = 0  # fps3010.h: 66
IfUsb = 1  # fps3010.h: 66
IfTcp = 2  # fps3010.h: 66
IfAll = 3  # fps3010.h: 66

FPS_InterfaceType = c_int  # fps3010.h: 66
FPS_PositionCallback = CFUNCTYPE(c_void_p, c_uint, c_uint, c_uint, POINTER(c_double) * 3)  # fps3010.h: 95

# fps3010.h: 115
FPS_discover = fps_lib.FPS_discover
FPS_discover.argtypes = [FPS_InterfaceType, POINTER(c_uint)]
FPS_discover.restype = c_int


# fps3010.h: 133
FPS_getDeviceInfo = fps_lib.FPS_getDeviceInfo
FPS_getDeviceInfo.argtypes = [c_uint, POINTER(c_int), c_char_p, POINTER(bln32)]
FPS_getDeviceInfo.restype = c_int


# fps3010.h: 146
FPS_connect = fps_lib.FPS_connect
FPS_connect.argtypes = [c_uint]
FPS_connect.restype = c_int


# fps3010.h: 155
FPS_disconnect = fps_lib.FPS_disconnect
FPS_disconnect.argtypes = [c_uint]
FPS_disconnect.restype = c_int


# fps3010.h: 166
FPS_getPosition = fps_lib.FPS_getPosition
FPS_getPosition.argtypes = [c_uint, c_uint, POINTER(c_double)]
FPS_getPosition.restype = c_int


# fps3010.h: 178
FPS_getPositions = fps_lib.FPS_getPositions
FPS_getPositions.argtypes = [c_uint, POINTER(c_double)]
FPS_getPositions.restype = c_int


# fps3010.h: 194
FPS_setPositionCallback = fps_lib.FPS_setPositionCallback
FPS_setPositionCallback.argtypes = [c_uint, c_uint, FPS_PositionCallback]
FPS_setPositionCallback.restype = c_int


# fps3010.h: 49
FPS_Ok = 0
FPS_Error = (-1)
FPS_Timeout = 1
FPS_NotConnected = 2
FPS_DriverError = 3
FPS_DeviceLocked = 7
FPS_Unknown = 8
FPS_NoDevice = 9


