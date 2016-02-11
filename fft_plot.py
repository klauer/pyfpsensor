from __future__ import print_function
import numpy as np
import matplotlib.pyplot as plt


def fftplot(data, left_indices, right_indices=[],
            xlabel=None, left_label='',
            right_label='', x_index=0,
            left_colors='bgc', right_colors='rmk',
            remove_dc=True, column_names={},
            scale=1.0):
    data = np.asarray(data)

    x_axis = data[x_index, :]
    all_indices = set(left_indices + right_indices)

    start_x = x_axis[0]
    end_x = x_axis[-1]
    step_x = np.average(np.diff(x_axis))
    print('x step', step_x)
    new_x = np.arange(start_x, end_x, step_x)

    freqs = np.fft.rfftfreq(len(x_axis), step_x)

    spectra = np.zeros((len(freqs), max(all_indices) + 1), dtype=float)
    for col in all_indices:
        interpolated = np.interp(new_x, x_axis, data[col, :] * scale)
        fft = np.fft.rfft(interpolated)
        spectra[:len(fft), col] = np.abs(fft) / len(fft)

    # Remove DC component
    if remove_dc:
        data = spectra[1:, :]
        x_axis = freqs[1:]
    else:
        data = spectra
        x_axis = freqs

    if xlabel is None:
        xlabel = 'Frequency [Hz]'

    # fig, ax1 = plt.subplots()
    # fig = plt.gcf()
    ax1 = plt.gca()
    if left_indices:
        for idx, color in zip(left_indices, left_colors):
            ax1.plot(x_axis, data[:, idx], color, label=column_names.get(idx, str(idx)),
                     alpha=0.7)
        ax1.set_xlabel(xlabel)
        ax1.set_ylabel(left_label)
        for tl in ax1.get_yticklabels():
            tl.set_color(left_colors[0])

    ax2 = None
    if right_indices:
        ax2 = ax1.twinx()
        for idx, color in zip(right_indices, right_colors):
            ax2.plot(x_axis, data[:, idx], color, label=column_names.get(idx, str(idx)),
                     alpha=0.4)
        ax2.set_ylabel(right_label)
        for tr in ax2.get_yticklabels():
            tr.set_color(right_colors[0])

    plt.xlim(min(x_axis), max(x_axis))
    return ax1, ax2


def plot_file(fn):
    data = np.load(fn)
    # n_cols = np.shape(data)[1]
    # x = data[0, :]
    # cols = [data[i, :] for i in range(1, n_cols)]
    print(data[0, :10])
    fftplot(data, [1], [2], column_names={1: 'x', 2: 'y'},
            scale=1.0)
    plt.show()


if __name__ == '__main__':
    plot_file('test.npy')
