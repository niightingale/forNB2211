
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
def storeData(readings, title): #here we make a function to save the data we measure in a npz file
    np.savez('m_' + title, readings)

def loadDataEx(mode = 'normal', f_cutoff = 10, s_window = 10, inject = '') -> tuple: #this function loads the data of a selected measurement and it allows the data to be filtered before being plotted.
#we use mode to determine if we get a filtered plot; normal is unfiltered; LPF gives a low pass filter plot.
#we use f_cutoff to determine the cutoff frequency when using LPF.
#we use s_window to determine the width of the window.
#we use inject to give the name of the file we want to load.
    pathToLoad = input('Insert file path without extensions')
    tmp = np.load('m_' + pathToLoad + '.npz')
    reading0 = tmp['arr_0']

    if(mode == 'normal'): #here we load "normal"
        plotData(reading0, pathTitle = pathToLoad, extra= 'raw' + ', ' + inject)
        
    elif(mode == 'LPF'): #here we load as if a Lowpass filter is applied 
        reading0_filtered = np.copy(reading0)

        #the filter
        lpf = signal.butter(10, f_cutoff, 'low', fs = 3000, output='sos')

        #here the data is filtered
        filtered = signal.sosfilt(lpf, reading0, axis = 0)
        reading0_filtered = filtered

        #here we filter the data of the temperature
        data_line = reading0[:,0,2]
        filtered = signal.sosfilt(lpf, data_line)
        reading0_filtered[:,0,2] = filtered 
        
        reading0 = reading0_filtered

        plotData(reading0, pathTitle = pathToLoad, extra = 'LPF, fc = ' + str(f_cutoff) + ', ' + inject)

    elif(mode == 'WINDOW'): #here we take the moving average of the data
        reading0_averaged = np.copy(reading0)
        
        #convolution
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

        
def plotData(data, pathTitle = '<memory>', extra = '') -> tuple: #this function is used to plot the data selected
#data is used to call the 3D numpy array that will be plotted
#pathTitle is used to call the name of the data file
#extra is used to put extra information on the plot
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

def measure(length = 25): #here we measure the passing through of light through the sample, it also measures the temperature.
#A0 is for the measured light and A1 is for the temperature
#D10 is used for red light; D9 for blue light; D8 for green light.
#length is used to determine the amount of samples

    #we define the name of the file
    global measurement_title 
    measurement_title = input('Enter file name: ')

    plt.close('all')
    arduino = pyfirmata.ArduinoNano('COM4') # might be another comport numer in your case
    time.sleep(1)

    it = pyfirmata.util.Iterator(arduino)
    it.start()

    #read 
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

    ai0 = arduino.get_pin('a:0:i')  #measurements of the light
    ai2 = arduino.get_pin('a:1:i')  #temperature measurement
    ai3 = arduino.get_pin('a:2:i')  #on/off switch; used only by achere, can be ignored.
    time.sleep(0.1) 

    num_avg = 10

    #wait; 
    small_delay = 0.05 #the time it waits between measurements of different colour and before and after a temperature measurement
    long_delay = 0.01 #the waiting time between measurement cycles
    
    ## ! small_delay needs to be at least 0.05, otherwise it will not end well
   
    #actual measuring
    start = time.time()
    for ii in range(num):
        # PAUSE CHECK
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
            time.sleep(small_delay) #when waiting a little the voltages will stabilize when switching between temp. and light measurement, temp. will be more stable
            #reading the temperature
            if jj == 0:
                avg_vals = []
                for n in range(num_avg):
                    temp = ai2.read()
                    avg_vals.append(temp)
                    time.sleep(0.001)
                reading0[ii,jj,2] = 500*np.mean(avg_vals)
            time.sleep(small_delay)
            
            #which colour when
            supply = pinBLUE
            if jj == 0: supply = pinBLUE
            elif jj == 1: supply = pinGREEN
            elif jj == 2: supply = pinRED
            supply.write(1) #supplies voltage, set to 0 when disconnecting the LED
            time.sleep(small_delay)

            #measure light
            reading0[ii,jj,0] = ai0.read()*10
            currentTime = time.time()
            reading0[ii,jj,1] = currentTime - start 
            time.sleep(small_delay)
            supply.write(0) #no supply
        
        #When stopping before the determined time, we save the data after every cycle
        reading0_preliminary = reading0[0:ii, :, :]

        storeData(reading0_preliminary, measurement_title)
        time.sleep(long_delay)
    
    #buzzer sound for determined ending
    for ii in range(3):
        pinBEEP.write(0.2)
        time.sleep(0.08)
        pinBEEP.write(0)
        time.sleep(0.4)

    arduino.sp.close()

#simple data loading and plotting
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
measure(200)

#%% LOADING DATA
loadData()

#%% LOADING NEW DATA
loadDataEx(mode = 'WINDOW', f_cutoff=400,s_window= 100, inject = 'Test')