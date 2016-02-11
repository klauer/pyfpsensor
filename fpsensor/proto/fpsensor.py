from __future__ import print_function
import socket
import threading
import time
import numpy as np

from ctypes import (c_int32, sizeof)

from .telegram import (REASON_OK, reason_strings, MAXSIZE)
from .telegram import (UcTelegram, UcGetTelegram, UcSetTelegram,
                       telegram_types, data_offsets)
from .telegram import (ID_FPS_CHAN_POSITION, ID_FPS_SYNC_POS, ID_FPS_TELL_OFF)


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
        if tel.reason != REASON_OK:
            print('response', reason_strings.get(tel.reason, None))
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
            print('unknown addr response (0x{0.address:x}:{0.index:d}) '
                  'data={1:s}?'.format(tel, list(tel.data)))
            print('telegram:', tel)

    def _receive_loop(self):
        # use a single buffer for the base telegram + the upcast one
        buf = bytearray(MAXSIZE)

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

            data_size = ((base_tel.length - data_offset) >> 2)
            # data_size /= sizeof(int32) ?

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
                #     print('[%s] %s -> %s'
                #           '' % (tel.address, old_value, tel.data[0]))

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
        tel = self._set_telegram(address=0x669, index=0,
                                 data=[int(bool(enabled))])
        self._send(tel)

    def zero(self, axis):
        tel = self._set_telegram(address=0x60d, index=int(axis), data=[1])
        self._send(tel)

    def zero_all(self):
        for axis in range(3):
            self.zero(axis)
