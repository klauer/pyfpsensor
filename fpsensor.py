from __future__ import print_function
import socket
import ctypes
import threading
import time
import numpy as np
import os

from ctypes import (c_int32, sizeof)

import uc

# Maximum number of axes
#
#    In telegrams where an index field is used to select an axis
#    the index must be in the range of 0 ... FPS_AXIS_COUNT-1 .
FPS_AXIS_COUNT = 0x3

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
        _opcode = uc.SET
        max_data_size = int((uc.MAXSIZE - sizeof(UcTelegram)) / sizeof(c_int32))
        _fields_ = (UcTelegram._fields_ +
                    [('data', c_int32 * data_size),
                     ]
                    )

    assert data_size <= _UcSetTelegram.max_data_size, \
        'Requested beyond maximum data size'

    return _UcSetTelegram


class UcGetTelegram(ctypes.Structure):
    _opcode = uc.GET
    data_size = 0
    _fields_ = list(UcTelegram._fields_)


def UcAckTelegram(data_size):
    class _UcAckTelegram(ctypes.Structure):
        _opcode = uc.ACK
        max_data_size = int((uc.MAXSIZE - sizeof(UcTelegram) - sizeof(c_int32))
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
        _opcode = uc.TELL
        max_data_size = int((uc.MAXSIZE - sizeof(UcTelegram))
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
    uc.SET: UcSetTelegram,
    uc.GET: lambda length: UcGetTelegram,
    uc.ACK: UcAckTelegram,
    uc.TELL: UcTellTelegram,
}

data_offsets = {id_: (type_gen(1).data.offset - UcTelegram.opcode.offset)
                for id_, type_gen in telegram_types.items()
                if id_ not in (uc.GET, )}

data_offsets[uc.GET] = None


def upcast_response(buf, expected_seq=None):
    p_base_tel = ctypes.cast(buf, ctypes.POINTER(UcTelegram))
    base_tel = p_base_tel.contents

    print(base_tel)

    if expected_seq is not None:
        if base_tel.sequence_num != expected_seq:
            raise ValueError('Sequence number unexpected?')

    length = base_tel.length
    if length > len(buf) or length > uc.MAXSIZE:
        raise ValueError('Buffer size too small / bad length?'
                         '(buflen=%d packet length=%d)' % (len(buf), length))

    data32_len = (length - sizeof(UcTelegram)) >> 2

    print('length', data32_len, sizeof(UcTelegram), length)

    if base_tel.opcode == uc.SET:
        tel = UcSetTelegram(data32_len)
    elif base_tel.opcode == uc.GET:
        tel = UcGetTelegram
    elif base_tel.opcode == uc.ACK:
        tel = UcAckTelegram(data32_len)
    elif base_tel.opcode == uc.TELL:
        tel = UcTellTelegram(data32_len)
    else:
        raise ValueError('Unknown telegram opcode=%d' % base_tel.opcode)

    p_tel = ctypes.cast(buf, ctypes.POINTER(tel))
    return p_tel.contents


class FPSensor(object):
    def __init__(self, host, port=2101):
        self._host = host
        self._port = port

        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._s.connect((self._host, self._port))
        self._seq = 129

        # self._requests = {}
        self._thread = None
        self._positions = [0.0, 0.0, 0.0]
        self._running = False
        self.data = {}
        self._s_lock = threading.Lock()
        self.positions = np.zeros((4, 20000), dtype=np.float)

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def socket(self):
        return self._s

    @property
    def _seq_num(self):
        self._seq = ((self._seq + 1) % 10000) + 1
        return self._seq

    def _get_telegram(self, address=0, index=0):
        tel = UcGetTelegram()
        tel.length = sizeof(tel) - sizeof(c_int32)
        tel.opcode = tel._opcode
        tel.address = address
        tel.index = index
        tel.sequence_num = self._seq_num
        return tel

    def _set_telegram(self, address=0, index=0, data=[]):
        tel = UcSetTelegram(len(data))()
        tel.length = sizeof(tel) - sizeof(c_int32)
        tel.opcode = tel._opcode
        tel.address = address
        tel.index = index
        tel.sequence_num = self._seq_num

        for i, val in enumerate(data):
            tel.data[i] = val
        return tel

    def _check_response(self, tel):
        reasons = {uc.REASON_OK: 'ok',
                   uc.REASON_ADDR: 'invalid address',
                   uc.REASON_RANGE: 'value out of range',
                   uc.REASON_IGNORED: 'telegram was ignored',
                   uc.REASON_VERIFY: 'verification of data failed',
                   uc.REASON_TYPE: 'wrong data type',
                   uc.REASON_UNKNW: 'unknown error',
                   }

        if tel.reason != uc.REASON_OK:
            print('response', reasons.get(tel.reason, None))
        # req_num = tel.sequence_num
        # try:
        #     req, t0 = self._requests.pop(req_num)
        # except KeyError:
        #     print('Unknown response? seq=%d' % (tel.sequence_num, ))
        #     return

        # units of 0.1nm * 1e4 -> um
        if tel.address == ID_FPS_CHAN_POSITION:
            # print('Axis %d Position: %f' % (tel.index, tel.data[0] / 1e4))
            self._positions[tel.index] = tel.data[0] / 1e4
            self.query_position(tel.index)
        elif tel.address == ID_FPS_SYNC_POS:
            # print('data', list(tel.data))
            self._positions[0] = tel.data[0] / 1e6
            self._positions[1] = tel.data[2] / 1e6
            self._positions[2] = tel.data[4] / 1e6

            for i in range(4):
                self.positions[i, :-1] = self.positions[i, 1:]
                if i == 0:
                    self.positions[i, -1] = time.time()
                else:
                    self.positions[i, -1] = self._positions[i - 1]

            # print('Axis 0 Position: %f' % (pos, ))
            # print('Axis 1 Position: %f' % (tel.data[0] / 1e4))
            # print('Axis 2 Position: %f' % (tel.data[0] / 1e4))
        else:
            self.data[(tel.address, tel.index)] = list(tel.data)
            print('unknown addr response (0x{0.address:x}:{0.index:d}) data={1:s}?'.format(tel, list(tel.data)))
            print('telegram:', tel)

    def _receive_loop(self):
        # use a single buffer for the base telegram + the upcast one
        buf = bytearray(uc.MAXSIZE)

        base_tel = UcTelegram.from_buffer(buf)

        while self._running:
            self._s.recv_into(base_tel, UcTelegram.address.offset)

            if base_tel.length <= 0:
                print('? length=', base_tel.length)
                continue
            elif base_tel.opcode not in telegram_types:
                print('? unknown telegram type?', base_tel.opcode)
                continue

            tel_type = telegram_types[base_tel.opcode]
            data_offset = data_offsets[base_tel.opcode]

            data_size = ((base_tel.length - data_offset) >> 2)  # / sizeof(int32)

            tel = tel_type(data_size).from_buffer(buf)

            # length doesn't include itself
            mv = memoryview(buf)
            self._s.recv_into(mv[UcTelegram.address.offset:],
                              tel.length - 4
                              )

            # TODO make classes top-level, subclass, etc.
            if 'Ack' in tel.__class__.__name__:
                self._check_response(tel)
            else:
                pass
                # if tel.index == 0:
                #     print(tel)

                # old_value = self.data.get((tel.address, tel.index), None)
                # if tel.index == 0 and old_value != tel.data[0]:
                #     print('[%s] %s -> %s' % (tel.address, old_value, tel.data[0]))

            self.data[(tel.address, tel.index)] = tel.data[0]

            # for id_, (req, t0) in list(self._requests.items()):
            #     if (time.time() - t0) > 1.0:
            #         # self._requests.pop(id_)

            #         req.sequence_num = self._seq_num
            #         self._requests[req.sequence_num] = (req, time.time())
            #         self._send(req)

    def _send(self, buf):
        with self._s_lock:
            self._s.sendall(buf)

    def query_position(self, axis):
        tel = self._get_telegram(address=ID_FPS_CHAN_POSITION, index=axis)
        # self._requests[tel.sequence_num] = (tel, time.time())
        self._send(tel)

    def query_positions(self):
        tel = self._get_telegram(address=ID_FPS_SYNC_POS, index=0)
        # self._requests[tel.sequence_num] = (tel, time.time())
        self._send(tel)

    def run(self):
        if self._thread is not None:
            return

        self._running = True

        self._thread = threading.Thread(target=self._receive_loop)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        self._running = False
        self._thread = None

    def tell_off(self):
        tel = self._set_telegram(address=ID_FPS_TELL_OFF, index=0, data=[1])
        # self._requests[tel.sequence_num] = (tel, time.time())
        self._send(tel)

    def align(self, enabled):
        tel = self._set_telegram(address=0x669, index=0, data=[int(bool(enabled))])
        self._send(tel)

    def zero(self, axis):
        tel = self._set_telegram(address=0x60d, index=int(axis), data=[1])
        self._send(tel)

    def zero_all(self):
        for axis in range(3):
            self.zero(axis)


def running_mean(x, N):
    x = np.asarray(x)
    nx = len(x)

    if len(x) < N:
        return np.array(x)

    ret = np.zeros(nx, dtype=float)
    for i in range(0, N):
        sub = x[0:i + 1]
        ret[i] = np.sum(sub) / len(sub)

    for i in range(N, len(x)):
        sub = x[i:i + N]
        ret[i] = np.sum(sub) / len(sub)
    return ret

# def running_mean(x, N):
#     return np.convolve(x, np.ones((N, )) / N, mode='same')


fps = FPSensor('10.3.3.41')
fps.run()
fps.tell_off()


if False:
    # fps.align(True)
    tel = fps._get_telegram(address=0x68e)
    fps._send(tel)

    # fps.zero_all()
    time.sleep(1.0)
    print('sample time', fps.data[(0x68e, 0)] / 97.65625, 'ms')

    tel = fps._set_telegram(address=0x68e, data=[64])
    fps._send(tel)

    time.sleep(0.1)

    for key, value in sorted(fps.data.items()):
        print(hex(key[0]), '(', key[1], ') =', value)

    import sys
    sys.exit(0)


# fps.query_positions()
# for i in range(3):
#     fps.query_position(i)

addrs = [1661, 1662, 1663, 1664, 1689, 1690, ]

time.sleep(0.1)

import matplotlib.pyplot as plt
from fft_plot import fftplot

plt.ion()
plt.show()


def plot_thread():
    while True:
        plt.figure(0)
        plt.clf()
        idx, = np.where(fps.positions[0, :] > 0)
        pos = fps.positions[:, idx]
        plt.plot(pos[0, :], pos[1, :], label='Axis 1')
        # plt.plot(pos[1, :], label='Axis 2')
        # plt.plot(pos[2, :], label='Axis 3')
        plt.xlim(pos[0, 0], pos[0, -1])

        avg_x = running_mean(pos[1, :], 100)
        plt.plot(pos[0, :len(avg_x)], avg_x, label='Axis 1 (100pts)')

        peak_peak = 2. * (np.sum(np.abs(pos[1, :] - avg_x)) / len(avg_x))
        ts = 1000.0 * np.average(np.diff(pos[0, :]))
        plt.title('estimated sample time: {0:.2f} ms\n'
                  'peak-peak {1:.1f}nm'.format(ts, peak_peak * 1000.0)
                  )

        np.save("interf_data.np", pos)

        if 0:
            plt.figure(1)
            plt.clf()
            fftplot(pos, [1], [2], column_names={1: 'x', 2: 'y'},
                    scale=1000.0,
                    )

            plt.title('FFT [nm] vs [Hz]')
        plt.pause(0.5)

_plot_thread = threading.Thread(target=plot_thread)
_plot_thread.daemon = True
_plot_thread.start()

try:
    i = 0
    while True:
        # info = ['%d' % fps.data[(addr, 0)] for addr in addrs]
        # info = []
        # info.extend(['%.3f' % pos for pos in fps._positions])
        # print('\r' + '\t'.join(info), end=' ' * 20)
        # print('\n' + '\t'.join(info))

        fps.query_positions()

        i += 1
        time.sleep(0.005)

        if (i % 5) == 0:
            os.system('clear')
            for i in range(2):
                for addr, idx in sorted(fps.data.keys()):
                    if idx != i:
                        continue

                    value = fps.data[(addr, idx)]
                    print('[%s:%d] %s' % (addr, i, value))

except KeyboardInterrupt:
    pass
finally:
    time.sleep(0.1)
    fps.stop()
