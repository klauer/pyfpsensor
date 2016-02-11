from __future__ import print_function
import threading
import ctypes
import functools
import time
import logging
import Queue
import numpy as np

from . import userlib
# from .userlib import FPSException


logger = logging.getLogger(__name__)


def _locked(fcn):
    @functools.wraps(fcn)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return fcn(self, *args, **kwargs)

    return wrapped


class FPSDevice(object):
    _TIME_SCALE_S = 1.024e-5
    _TIME_SCALE_MS = _TIME_SCALE_S * 1e3

    def __init__(self, lock, dev_num, ip_addr, id_num, connected):
        FPSDevice.instance = self  # TODO
        self._lock = lock
        self._dev_num = dev_num
        self._ip_addr = ip_addr
        self._id_num = id_num
        self._connected = connected
        self._monitoring = False
        self._sample_rate = None
        self._cb_queue = Queue.Queue()
        self._cb_thread = None

        self._reset()

    def _queue_handler(self):
        while self._monitoring:
            try:
                count, seq_idx, pos = self._cb_queue.get(timeout=0.05)
            except Queue.Empty:
                continue

            self._monitor(count, seq_idx, pos)

    def _reset(self):
        self._timestamp = None
        self._timestamps = []
        self._next_idx = None
        self._positions = [[] for i in range(3)]
        self._timestamps = []
        self._filter_size = 32
        self._filter_data = None
        self._filtered = None
        self._cb_queue = Queue.Queue()

    def _detached(self):
        '''device number handle is now stale'''
        self._lock = None
        # TODO

    def __str__(self):
        return '<FPSDevice dev_num={0._dev_num} ip_addr={0._ip_addr}' \
               ' id_num={0._id_num} connected={0._connected}>'.format(self)

    def connect(self):
        if self._connected:
            return

        userlib.connect(self._dev_num)
        self._connected = True

    def disconnect(self):
        if not self._connected:
            return

        userlib.disconnect(self._dev_num)
        self._connected = False

    @property
    def positions(self):
        pos = (ctypes.c_double * 3)()
        userlib.get_positions(self._dev_num, ctypes.byref(pos))
        return pos[:]

    @property
    def sample_rate(self):
        return self._sample_rate * self._TIME_SCALE_MS

    def _monitor(self, count, seq_idx, positions):
        dt = self.sample_rate
        if self._next_idx is not None and self._next_idx < seq_idx:
            print('missed position: got ', seq_idx, 'expected', self._next_idx)
            print('sequence difference: ', (seq_idx - self._next_idx))
            self._timestamp += dt * (seq_idx - self._next_idx)

        if self._timestamp is None:
            self._timestamp = 0

        self._next_idx = seq_idx + count

        for i, all_pos in enumerate(self._positions):
            all_pos.extend(positions[i, :])

        if self._filter_data is None and self._filter_size > 0:
            self._filter_data = [[positions[i, 0]] * self._filter_size
                                 for i in range(3)]
            self._filtered = [[] for i in range(3)]

        if self._filter_size > 0:
            for i, filt in enumerate(self._filter_data):
                for pos in positions[i, :]:
                    filt[:-1] = filt[1:]
                    filt[-1] = pos
                    self._filtered[i].append(np.average(filt))

        for i in range(count):
            self._timestamps.append(self._timestamp * 1e-3)
            self._timestamp += dt

    def monitor(self, sample_rate=1.0, wait_for=None, wait_timestamp=None):
        '''
        sample_rate: milliseconds
        '''
        if self._monitoring:
            return

        if self._cb_thread is not None:
            self._cb_thread.join()

        self._reset()
        self._sample_rate = int(float(sample_rate) / self._TIME_SCALE_MS)

        assert 1 <= self._sample_rate <= 100000, \
            'Invalid sample rate (%d)' % self._sample_rate

        def callback(*args):
            try:
                dev_num, count, seq_idx, positions = args
                if dev_num != self._dev_num:
                    return
                elif not self._monitoring:
                    return
                elif count <= 0:
                    print('count=', count)
                    return

                # pos = np.array([positions[i][:count] for i in range(3)])
                pos = np.array([[0] * count for i in range(3)])
                queue_item = (count, seq_idx, pos)
                self._cb_queue.put(queue_item)
            except Exception as ex:
                print('callback failure', ex, ex.__class__.__name__)

        self._callback_fcn = userlib.PositionCallback(callback)
        userlib.set_position_callback(self._dev_num, self._sample_rate,
                                      self._callback_fcn)

        self._monitoring = True

        self._cb_thread = threading.Thread(target=self._queue_handler)
        self._cb_thread.daemon = True
        self._cb_thread.start()

        if wait_for is not None and wait_for > 0:
            while len(self._positions[0]) < wait_for:
                time.sleep(0.05)

        elif wait_timestamp is not None and wait_timestamp > 0:
            wait_timestamp *= 1e3
            while self._timestamp < wait_timestamp:
                time.sleep(0.05)

    def stop(self):
        if not self._monitoring:
            return

        self._monitoring = False
        # userlib.set_position_callback(self._dev_num, self._sample_rate, None)
        if self._cb_thread is not None:
            self._cb_thread.join()
            self._cb_thread = None

    @property
    def position_data(self):
        num_pos = len(self._positions[0])
        data = np.zeros((4, num_pos))
        data[0, :] = self._timestamps
        data[1, :] = self._positions[0]
        data[2, :] = self._positions[1]
        data[3, :] = self._positions[2]
        return data


class FPSensor(object):
    def __init__(self):
        self._lock = threading.Lock()
        self._devices = []

    def _clear_devices(self):
        for dev in self._devices:
            dev._detached()

        del self._devices[:]

    @_locked
    def _find_devices(self, interface, wait=True):
        dev_count = ctypes.c_uint()

        while True:
            userlib.discover(interface, ctypes.pointer(dev_count))

            if wait and dev_count.value <= 0:
                time.sleep(0.1)
            else:
                break

        self._clear_devices()
        dev_count = dev_count.value

        print('device count', dev_count)

        if dev_count <= 0:
            return self.devices

        for dev in range(dev_count):
            addr = ctypes.create_string_buffer(16)
            dev_id = ctypes.c_int()
            connected = ctypes.c_int()
            userlib.getDeviceInfo(dev, ctypes.pointer(dev_id), addr,
                                  ctypes.pointer(connected))

            device = FPSDevice(self._lock, dev, addr.value, dev_id.value,
                               connected.value)
            self._devices.append(device)

        return self.devices

    def find_tcp_devices(self, **kwargs):
        return self._find_devices(userlib.IfTcp, **kwargs)

    def find_devices(self, **kwargs):
        return self._find_devices(userlib.IfAll, **kwargs)

    def find_usb_devices(self, **kwargs):
        return self._find_devices(userlib.IfUsb, **kwargs)

    @property
    def devices(self):
        return list(self._devices)
