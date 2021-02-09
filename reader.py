
#%%
import pyfirmata
from scipy import signal
from scipy import stats
import math
import time
import matplotlib.pyplot as plt
import numpy as np
import threading

#%% FUNCTIONS
# FUNCTIONS
def storeData(readings, title):
    np.savez('m_' + title, readings)

def loadDataEx(mode = 'normal', f_cutoff = 10, s_window = 10, inject = '') -> tuple:
    """ LoadDataEx
    ----
    Loads the data of a specific measurement and allows it to be filtered before 
    being plotted.

    Parameters
    ----------
    > mode (string, optional) : The plotting mode. `Normal` gives us an unfiltered
    version of the plot, `LPF` gives us a lowpass filtered version.

    > f_cutoff (int, optional, only for LPF) : The cutoff frequency of the LPF.

    > s_window (int, optional, only for `WINDOW`) : The width of our window.

    Notes
    -----
    -

    """
    pathToLoad = input('Insert file path without extensions')
    tmp = np.load('m_' + pathToLoad + '.npz')
    reading0 = tmp['arr_0']

    # Standard Load
    if(mode == 'normal'):
        plotData(reading0, pathTitle = pathToLoad, extra= 'raw' + ', ' + inject)
    # LPF Load
    elif(mode == 'LPF'):
        reading0_filtered = np.copy(reading0)

        # FILTER SETUP
        lpf = signal.butter(10, f_cutoff, 'low', fs = 3000, output='sos')

        # Filtering Data
        filtered = signal.sosfilt(lpf, reading0, axis = 0)
        reading0_filtered = filtered

        # Filtering Temperature Data
        data_line = reading0[:,0,2]
        filtered = signal.sosfilt(lpf, data_line)
        reading0_filtered[:,0,2] = filtered 
        
        reading0 = reading0_filtered

        plotData(reading0, pathTitle = pathToLoad, extra = 'LPF, fc = ' + str(f_cutoff) + ', ' + inject)
    # Moving Average
    elif(mode == 'WINDOW'):
        reading0_averaged = np.copy(reading0)
        # CONVOLUTION SETUP
        window = np.ones(s_window)/s_window

        for ii in range(3):
            line = reading0[:,ii,0]
            line_averaged = np.convolve(line, window, mode ='same')
            reading0_averaged[:,ii,0]=line_averaged
        
        temp_line = reading0[:,0,2]
        temp_line_filtered = np.convolve(temp_line, window, mode = 'same')
        reading0_averaged[:,0,2] = temp_line_filtered

        reading0 = reading0_averaged

        plotData(reading0, pathTitle= pathToLoad, extra = 'WINDOW, len = ' + str(s_window) + ', ' + inject)

        
def plotData(data, pathTitle = '<memory>', extra = '') -> tuple:
    """ plotData
    ----
    Plots the transmission and temperature data of a measurement from memory.

    Parameters
    ----------
    > data (numpy array) : The 3D numpy array that we want to plot.

    > pathTitle (string, optional) : The name of the file from which it was loaded.
    If nothing is specified, `memory` will be used.

    > extra (string, optional) : Additional information to be
    put on the plot.

    Notes
    -----
    -

    """
    fig, ax1 = plt.subplots()
    
    ax1.set_xlabel('t (s)')
    ax1.set_ylabel('absolute signal')

    ax1.plot(data[:,0,1], data[:,0,0], 'b', label='460 nm', color='b')
    ax1.plot(data[:,1,1], data[:,1,0], 'g', label='520 nm', color='g')
    ax1.plot(data[:,2,1], data[:,2,0], 'r', label='645 nm', color='r')

    ax2 = ax1.twinx()

    ax2_col = 'tab:blue'
    ax2.set_ylabel('temperature (C)', color=ax2_col)

    ax2.plot(data[:,0,1], data[:,0,2], label='Temperature')
    ax2.tick_params(axis='y', labelcolor=ax2_col)

    ax1.legend(loc = 4)
    plt.title('Transmission plot: ' + pathTitle + ', ' + extra)
    plt.show()

    print('Blue Mean: ' + str(np.mean(data[:,0,0])))
    print('Green Mean: ' + str(np.mean(data[:,1,0])))
    print('Red Mean: ' + str(np.mean(data[:,2,0])))

def measure(length = 25):
    """ measure
    ----
    Does a measurement of the transmission of light through the sample, while also logging temperature.
    It uses the pins `D8`, `D9 ` and `D10` for respectively green, blue and red light. For measuring
    transmission, pin `A0` is used, while `A1` is used for measuring temperature.

    Parameters
    ----------
    > length (int, optional) : The lenght of the measurement in samples.

    Notes
    -----
    -

    """
    # Define Name
    global measurement_title 
    measurement_title = input('Enter file name: ')

    plt.close('all')
    arduino = pyfirmata.ArduinoNano('COM4') # might be another comport numer in your case
    time.sleep(1)

    it = pyfirmata.util.Iterator(arduino)
    it.start()

    # READINGS
    num = length
    global reading0 
    reading0 = np.zeros((num,3,3))

    pinRED = arduino.get_pin('d:10:o')
    pinRED.write(0)
    time.sleep(0.1)
    pinBLUE = arduino.get_pin('d:9:o')
    pinBLUE.write(0)
    time.sleep(0.1)
    pinGREEN = arduino.get_pin('d:8:o')
    pinGREEN.write(0)
    time.sleep(0.1)
    pinBEEP = arduino.get_pin('d:6:p')
    pinBEEP.write(0)
    time.sleep(0.1)

    ai0 = arduino.get_pin('a:0:i')  # Measurements
    ai2 = arduino.get_pin('a:1:i')  # Temperature Measurement
    ai3 = arduino.get_pin('a:2:i')  # Pause Button
    time.sleep(0.1) # Wait for definitions to apply

    # AVERAGING
    num_avg = 10

    # DELAYS
    small_delay = 0.05 # Delay Between measurements of different colour / before and after temp. measurement
    long_delay = 0.01 # Delay Between measurement cycles

    """ DELAYS
    DO NOT, decrease the small_delay under 0.05. This wil clause major bleed
    """

    # MEASURING ITSELF
    start = time.time()
    for ii in range(num):
        # PAUSE CHECK (SNIPPET 2)
        if ai3.read() > 0.8:
            isHigh = True
            while isHigh:
                time.sleep(0.05)
                pinBEEP.write(0.01)
                time.sleep(0.01)
                pinBEEP.write(0)
                if ai3.read() < 0.8:
                    isHigh = False
                    pinBEEP.write(0)
                    time.sleep(0.05)
        print(ii)
        for jj in range(3):
            time.sleep(small_delay)
            # Temperature Reading
            '''
            The delays before and after are required to allow time for voltages
            to stabilise between different types of measurements. This was found
            to give a more stable temperature reading.
            '''
            if jj == 0:
                avg_vals = []
                for n in range(num_avg):
                    temp = ai2.read()
                    avg_vals.append(temp)
                    time.sleep(0.001)
                reading0[ii,jj,2] = 500*np.mean(avg_vals)
            time.sleep(small_delay)
            
            # Defining Colour rotation
            supply = pinBLUE
            if jj == 0: supply = pinBLUE
            elif jj == 1: supply = pinGREEN
            elif jj == 2: supply = pinRED
            supply.write(1) # Supply ON
            time.sleep(small_delay)

            # Light Reading
            reading0[ii,jj,0] = ai0.read()
            currentTime = time.time()
            reading0[ii,jj,1] = currentTime - start 
            time.sleep(small_delay)
            supply.write(0) # Supply OFF
        
        # For early stop; Saving of data occurs after every cycle
        reading0_preliminary = reading0[0:ii, :, :]

        storeData(reading0_preliminary, measurement_title)
        time.sleep(long_delay)
    
    # BEEP for END (SNIPPET 1)
    for ii in range(3):
        pinBEEP.write(0.2)
        time.sleep(0.08)
        pinBEEP.write(0)
        time.sleep(0.4)

    arduino.sp.close()

    # STORING DATA
    #storeData(reading0, measurement_title)

# DEPRECATED FUNCTIONS
def loadData():
    pathToLoad = input('Insert file path without extensions')
    tmp = np.load('m_' + pathToLoad + '.npz')
    reading0 = tmp['arr_0']
    
    plt.figure(1)
    plt.title('Signal Strength')
    plt.xlabel('t (s)')
    plt.ylabel('absolute signal')

    plt.plot(reading0[:,0,1], reading0[:,0,0], 'b', label='460 nm')
    plt.plot(reading0[:,1,1], reading0[:,1,0], 'g', label='520 nm')
    plt.plot(reading0[:,2,1], reading0[:,2,0], 'r', label='645 nm')
    plt.legend()
    print('Blue Mean: ' + str(np.mean(reading0[:,0,0])))
    print('Green Mean: ' + str(np.mean(reading0[:,1,0])))
    print('Red Mean: ' + str(np.mean(reading0[:,2,0])))
    plt.show()

#%% MEASURING
measure(25)

#%% LOADING DATA
loadData()

#%% LOADING NEW DATA
loadDataEx(mode = 'WINDOW', f_cutoff=400,s_window= 1000, inject = 'Plot 7b')

# %%
tmp1 = np.load(r'm_j1.npz')
tmp3 = np.load(r'm_j1cont.npz')
read1 = tmp1['arr_0']
read3 = tmp3['arr_0']
read4 = np.vstack((read1, read3))
storeData(read4, 'j1_full')
tmp2 = np.load(r'm_yeast_17_01_1200_2.npz')
read2 = tmp2['arr_0']

read_cut = read1[0:12500,:,:]
#storeData(read_cut, 'j2_cut')

from scipy.stats import linregress
linregress(read_cut[:,2,1], read_cut[:,2,0])

# %% INFO
'''
-17/01 run > We used 11 mL of water, with 1.5 mL sugar and 0.5 mL yeast.
    We tracked for 1 full hour.
-23/01 run ? 7 mL of water, with 1.5 mL sugar and 0.5 mL yeast. (81000=9h) CRASHED
-30/01 run -> redo of 23/01
-04/02 run > 7 mL of water, 1 mL brown sugar, 1 mL yeast.

-dns_with > Using heater, greatly induces noise by satuarating the 5V rail as it 
pulls a great amperage (40 ohm).
-dns_without > Without using heater, almost no extra noise

-dnsl > Strobing light with the subcover closed at ~ 10 cm.
-dnswl > Only natural light with subcover closed.
-dnsclose > Completely closed.
'''
# %%
import concurrent.futures

def mainred():
    for ii in range(5):
        print('\nofiri')
        time.sleep(1)

def sidered():
    for jj in range(5):
        print('\nhoraw')
        time.sleep(1)

main = threading.Thread(target=mainred)
side = threading.Thread(target=sidered)

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    executor.submit(mainred)
    executor.submit(sidered)

'''
main.start()
side.start()

main.join()
side.join()
'''
#%%
plt.close('all')
arduino = pyfirmata.ArduinoNano('COM4') # might be another comport numer in your case
time.sleep(1)

it = pyfirmata.util.Iterator(arduino)
it.start()

pinner = arduino.get_pin('a:0:i')
time.sleep(0.1)

listoa = []

for tt in range(25):
    listoa.append(50*pinner.read())
    time.sleep(0.05)

plt.plot(listoa)
arduino.sp.close()

# %%
def cleanup():
    pathToLoad = input('Insert file path without extensions')
    tmp = np.load('m_' + pathToLoad + '.npz')
    reading0 = tmp['arr_0']

    reading0_cleaned = reading0[0:15000,:,:]
    storeData(reading0_cleaned, pathToLoad + 'cleaned')
cleanup()
# %%
arduino = pyfirmata.ArduinoNano('COM4') # might be another comport numer in your case
time.sleep(1)

it = pyfirmata.util.Iterator(arduino)
it.start()

pinread = arduino.get_pin('a:2:i')
pinbeep = arduino.get_pin('d:6:p')
pinbeep.write(0)
time.sleep(0.5)

while True:
    print(pinread.read())
    if pinread.read() > 0.8:
        pinbeep.write(0.05)
    else:
        pinbeep.write(0)
    time.sleep(0.01)


arduino.sp.close()
# %%
