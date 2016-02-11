'''Test of the tcp-based interface to the fps3010
'''

import os
import time
import threading

import numpy as np
import matplotlib.pyplot as plt

from fft_plot import fftplot
from fpsensor.proto import FPSensor


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


def simple_test(fps):
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


def plot_test():
    # fps.query_positions()
    # for i in range(3):
    #     fps.query_position(i)

    # addrs = [1661, 1662, 1663, 1664, 1689, 1690, ]
    time.sleep(0.1)

    plt.ion()
    plt.show()

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


simple_test()
