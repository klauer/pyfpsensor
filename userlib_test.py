'''Test of the userlib-based interface to the fps3010
'''
from __future__ import print_function
import time
from fpsensor.userlib import (FPSensor, FPSException)

import numpy as np
import matplotlib.pyplot as plt
from fft_plot import fftplot

plt.ion()

fps = FPSensor()


def plot_loop(dev):
    # t0 = time.time()
    # dev.monitor(sample_rate=0.6554, wait_for=2048)
    dev.monitor(sample_rate=2. * 0.3277, wait_timestamp=0.1)
    # t1 = time.time()
    dev.stop()
    # print(pos)
    # return

    data = dev.position_data
    # for i in range(num_pos):
    #     print('%-20s\t%f\t%f\t%f'
    #           '' % (dev._timestamps[i], dev._positions[0][i],
    #                 dev._positions[1][i], dev._positions[2][i],)
    #           )

    plt.figure(1)
    plt.clf()
    col_names = {1: 'x', 2: 'y', 3: 'z'}
    colors = 'bgk'
    ax1, ax2, freqs, spectra = fftplot(data, [1, 2, 3],
                                       column_names=col_names,
                                       left_label='Amplitude [nm]',
                                       scale=1.0,
                                       left_colors=colors)
    plt.xlim(0, 400)
    plt.ylim(0, 5.0)
    plt.draw()

    title = ['Sample rate: %f ms [data points=%d]'
             '' % (dev.sample_rate, len(data[0, :]))
             ]

    for i in range(1, 4):
        max_i = np.argmax(spectra[:, i])
        max_freq = freqs[max_i]
        nm = spectra[max_i, i]
        color = colors[i - 1]

        # title.append('%s[%f]=%f nm' % (col_names[i], max_freq, nm))
        # plt.axvline(max_freq)
        plt.text(max_freq + 1, 0.9 * nm, '%.1f Hz' % max_freq, color=color)
        # plt.text(max_freq + 1, 0.75 * nm, '%.2f nm' % nm, color=color)
        # plt.text(max_freq, 0, '%.1f Hz' % max_freq, color=color)

    plt.title('\n'.join(title))
    plt.legend(loc='best')
    plt.savefig('fft.png')

    plt.figure(2)
    plt.clf()
    ts = data[0, :]
    print('ts=%d filt=%d' % (len(ts), len(dev._filtered[0])))
    plt.plot(ts, dev._filtered[0])
    plt.plot(ts, data[1, :], alpha=0.1)

    plt.pause(0.1)
    plt.show()

    np.save('test', data)
    for i in range(3):
        print('average position (ax=%d)' % i, np.average(dev._positions[i]))
    # print('total positions in %g seconds: %d' % (t1 - t0, len(data[0, :])))
    # print('sample rate %f (%d)' % (dev.sample_rate, dev._sample_rate))
    dev._positions = [[] for i in range(3)]


if __name__ == '__main__':
    # for dev in fps.find_usb_devices():
    for dev in fps.find_tcp_devices():
        print('device', dev)
        while True:
            try:
                dev.connect()
            except FPSException as ex:
                print('Retrying connection (%s)' % (ex, ))
                time.sleep(0.1)
            else:
                break

        pos = dev.positions

        try:
            while True:
                plot_loop(dev)
        except KeyboardInterrupt:
            break
        finally:
            dev.disconnect()
