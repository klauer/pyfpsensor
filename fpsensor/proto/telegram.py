from __future__ import print_function
import socket
import ctypes
import threading
import time
import numpy as np
import os

from ctypes import (c_int32, sizeof)

# @brief Maximum size of a telegram
#
# Maximum size of a telegram including header (with length field) and data,
# in bytes.
#
MAXSIZE = 512

# @name OpCodes
#
# These constants are used to identify the protocol elements and fit to the
# opcode field of the @ref UcTelegram "telegram header".
#
SET = 0       # Set telegram
GET = 1       # Get telegram
ACK = 3       # Ack (acknowledge) telegram
TELL = 4      # Tell (event) telegram


# @name Reason codes
#
# These constants are used to notify about errors in the processing of
# @ref UcSetTelegram "Set" and @ref UcGetTelegram "Get" telegrams
# They are found in the reason field of the @ref UcAckTelegram "Ack Telegram".
REASON_OK      = 0  # All ok
REASON_ADDR    = 1  # Invalid address
REASON_RANGE   = 2  # Value out of range
REASON_IGNORED = 3  # Telegram was ignored
REASON_VERIFY  = 4  # Verify of data failed
REASON_TYPE    = 5  # Wrong type of data
REASON_UNKNOWN   = 99 # unknown error


reason_strings = {
    REASON_OK: 'ok',
    REASON_ADDR: 'invalid address',
    REASON_RANGE: 'value out of range',
    REASON_IGNORED: 'telegram was ignored',
    REASON_VERIFY: 'verification of data failed',
    REASON_TYPE: 'wrong data type',
    REASON_UNKNW: 'unknown error',
}

# Maximum number of axes
#
#    In telegrams where an index field is used to select an axis
#    the index must be in the range of 0 ... FPS_AXIS_COUNT-1 .
FPS_AXIS_COUNT = 3

# Single position, low resolution
#
#    Read the position of a single axis.
#    The axis is selected by the index field of the telegram.
#    The answer will be a single Int32 item that contains the
#    position in units of 100pm.
ID_FPS_CHAN_POSITION = 0x688

# Synchronized positions, high resolution
#
# Read the position of all three axes measured at the same time.
# The index field must be 0.
# The answer will be a telegram of six data elements with the
# following meaning:
#
#   data[0]: lower 32 bit of position 1 \n
#   data[1]: upper 16 bit of position 1 \n
#   data[2]: lower 32 bit of position 2 \n
#   data[3]: upper 16 bit of position 2 \n
#   data[4]: lower 32 bit of position 3 \n
#   data[5]: upper 16 bit of position 3 \n
#   The three positions come in units of 1 pm.
ID_FPS_SYNC_POS = 0x692

ID_FPS_TELL_OFF = 0x145  # idx = 0 (what does this do?)


class UcTelegram(ctypes.Structure):
    _fields_ = [('length', c_int32),
                ('opcode', c_int32),
                ('address', c_int32),
                ('index', c_int32),
                ('sequence_num', c_int32)
                ]

    def __str__(self):
        return '<UcTelegram length={0.length} opcode={0.opcode} ' \
               'address={0.address} index={0.index} ' \
               'sequence_num={0.sequence_num}>'.format(self)


def UcSetTelegram(data_size):
    class _UcSetTelegram(ctypes.Structure):
        _opcode = SET
        max_data_size = int((MAXSIZE - sizeof(UcTelegram)) / sizeof(c_int32))
        _fields_ = (UcTelegram._fields_ +
                    [('data', c_int32 * data_size),
                     ]
                    )

    assert data_size <= _UcSetTelegram.max_data_size, \
        'Requested beyond maximum data size'

    return _UcSetTelegram


class UcGetTelegram(ctypes.Structure):
    _opcode = GET
    data_size = 0
    _fields_ = list(UcTelegram._fields_)


def UcAckTelegram(data_size):
    class _UcAckTelegram(ctypes.Structure):
        _opcode = ACK
        max_data_size = int((MAXSIZE - sizeof(UcTelegram) - sizeof(c_int32))
                            / sizeof(c_int32))
        _fields_ = (UcTelegram._fields_ +
                    [('reason', c_int32),
                     ('data', c_int32 * data_size),
                     ]
                    )

        def __str__(self):
            return '<UcAckTelegram seq={0.sequence_num} addr=0x{0.address:x} reason={0.reason} ' \
                   'datalen={1} data={2}>'.format(self, len(self.data), self._data_str)

        @property
        def _data_str(self):
            return ' '.join(('%d' % c for c in self.data))

    assert data_size <= _UcAckTelegram.max_data_size, \
        'Requested beyond maximum data size'
    return _UcAckTelegram


def UcTellTelegram(data_size):
    class _UcTellTelegram(ctypes.Structure):
        _opcode = TELL
        max_data_size = int((MAXSIZE - sizeof(UcTelegram))
                            / sizeof(c_int32))
        _fields_ = (UcTelegram._fields_ +
                    [('data', c_int32 * data_size),
                     ]
                    )

        def __str__(self):
            return '<UcTellTelegram seq={0.sequence_num} ' \
                   'address=0x{0.address:X} index={0.index} datalen={1} data={2}>' \
                   .format(self, len(self.data), self._data_str)

        @property
        def _data_str(self):
            return ' '.join(('%d' % c for c in self.data))

    assert data_size <= _UcTellTelegram.max_data_size, \
        'Requested beyond maximum data size'
    return _UcTellTelegram


telegram_types = {
    SET: UcSetTelegram,
    GET: lambda length: UcGetTelegram,
    ACK: UcAckTelegram,
    TELL: UcTellTelegram,
}

data_offsets = {id_: (type_gen(1).data.offset - UcTelegram.opcode.offset)
                for id_, type_gen in telegram_types.items()
                if id_ not in (GET, )}

data_offsets[GET] = None


def upcast_response(buf, expected_seq=None):
    p_base_tel = ctypes.cast(buf, ctypes.POINTER(UcTelegram))
    base_tel = p_base_tel.contents

    print(base_tel)

    if expected_seq is not None:
        if base_tel.sequence_num != expected_seq:
            raise ValueError('Sequence number unexpected?')

    length = base_tel.length
    if length > len(buf) or length > MAXSIZE:
        raise ValueError('Buffer size too small / bad length?'
                         '(buflen=%d packet length=%d)' % (len(buf), length))

    data32_len = (length - sizeof(UcTelegram)) >> 2

    print('length', data32_len, sizeof(UcTelegram), length)

    if base_tel.opcode == SET:
        tel = UcSetTelegram(data32_len)
    elif base_tel.opcode == GET:
        tel = UcGetTelegram
    elif base_tel.opcode == ACK:
        tel = UcAckTelegram(data32_len)
    elif base_tel.opcode == TELL:
        tel = UcTellTelegram(data32_len)
    else:
        raise ValueError('Unknown telegram opcode=%d' % base_tel.opcode)

    p_tel = ctypes.cast(buf, ctypes.POINTER(tel))
    return p_tel.contents
