from threading import Thread
import serial
import time
import collections
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import struct
import copy
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter as Tk
from tkinter.ttk import Frame
import pandas as pd


class serialPlot:
    def __init__(self, serialPort='COM3', serialBaud=38400, plotLength=100, dataNumBytes=2, numPlots=1):
        self.port = serialPort
        self.baud = serialBaud
        self.plotMaxLength = plotLength
        self.dataNumBytes = dataNumBytes
        self.numPlots = numPlots
        self.rawData = bytearray(numPlots * dataNumBytes)
        self.dataType = None
        if dataNumBytes == 2:
            self.dataType = 'h'     # 2 byte integer
        elif dataNumBytes == 4:
            self.dataType = 'f'     # 4 byte float
        self.data = []
        for i in range(numPlots):   # give an array for each type of data and store them in a list
            self.data.append(collections.deque([0] * plotLength, maxlen=plotLength))
        self.isRun = True
        self.isReceiving = False
        self.thread = None
        self.plotTimer = 0
        self.previousTimer = 0
        # self.csvData = []

        print('Trying to connect to: ' + str(serialPort) + ' at ' + str(serialBaud) + ' BAUD.')
        try:
            self.serialConnection = serial.Serial(serialPort, serialBaud, timeout=4)
            print('Connected to ' + str(serialPort) + ' at ' + str(serialBaud) + ' BAUD.')
        except:
            print("Failed to connect with " + str(serialPort) + ' at ' + str(serialBaud) + ' BAUD.')

    def readSerialStart(self):
        if self.thread == None:
            self.thread = Thread(target=self.backgroundThread)
            self.thread.start()
            # Block till we start receiving values
            while self.isReceiving != True:
                time.sleep(0.1)

    def getSerialData(self, frame, lines, lineValueText, lineLabel, timeText):
        currentTimer = time.clock()
        self.plotTimer = int((currentTimer - self.previousTimer) * 1000)     # the first reading will be erroneous
        self.previousTimer = currentTimer
        timeText.set_text('Plot Interval = ' + str(self.plotTimer) + 'ms')
        privateData = copy.deepcopy(self.rawData[:])    # so that the 3 values in our plots will be synchronized to the same sample time
        for i in range(self.numPlots):
            data = privateData[(i*self.dataNumBytes):(self.dataNumBytes + i*self.dataNumBytes)]
            value,  = struct.unpack(self.dataType, data)
            self.data[i].append(value)    # we get the latest data point and append it to our array
            lines[i].set_data(range(self.plotMaxLength), self.data[i])
            lineValueText[i].set_text('[' + lineLabel[i] + '] = ' + str(value))
        # self.csvData.append([self.data[0][-1], self.data[1][-1], self.data[2][-1]])

    def backgroundThread(self):    # retrieve data
        time.sleep(1.0)
        self.serialConnection.reset_input_buffer()
        while (self.isRun):
            self.serialConnection.readinto(self.rawData)
            self.isReceiving = True
            #print(self.rawData)

    def sendSerialData(self, data):
        self.serialConnection.write(data.encode('utf-8'))

    def close(self):
        self.isRun = False
        self.thread.join()
        self.serialConnection.close()
        print('Disconnected...')
        # df = pd.DataFrame(self.csvData)
        # df.to_csv('/home/rikisenia/Desktop/data.csv')


class Window(Frame):
    def __init__(self, figure, master, SerialReference):
        Frame.__init__(self, master)
        self.entry = None
        self.setPoint = None
        self.master = master        # a reference to the master window
        self.serialReference = SerialReference      # keep a reference to our serial connection so that we can use it for bi-directional communicate from this class
        self.initWindow(figure)     # initialize the window with our settings

    def initWindow(self, figure):
        self.master.title("Real Time Plot")
        canvas = FigureCanvasTkAgg(figure, master=self.master)
        toolbar = NavigationToolbar2TkAgg(canvas, self.master)
        canvas.get_tk_widget().pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)   # this is frame1

        # create a new frame to place our widgets
        frame2 = Frame(self.master)
        frame2.pack(side=Tk.RIGHT)

        lbl1 = Tk.Label(frame2, text="Kp")
        lbl1.grid(row=0, column=0, sticky=Tk.W, padx=5, pady=5)
        self.entry1 = Tk.Entry(frame2, width=5)
        self.entry1.insert(0, '1.0')     # (index, string)
        self.entry1.grid(row=0, column=1, padx=5, pady=5)
        SendButton1 = Tk.Button(frame2, text='Set Kp', command=self.sendKpToMCU, width=7)
        SendButton1.grid(row=0, column=2, padx=5, pady=5)

        lbl2 = Tk.Label(frame2, text="Mtr Spd")
        lbl2.grid(row=1, column=0, sticky=Tk.W, padx=5, pady=5)
        self.entry2 = Tk.Entry(frame2, width=5)
        self.entry2.insert(0, '50')  # (index, string)
        self.entry2.grid(row=1, column=1, padx=5, pady=5)
        SendButton2 = Tk.Button(frame2, text='Set Spd', command=self.sendSpdToMCU, width=7)
        SendButton2.grid(row=1, column=2, padx=5, pady=5)

        SendButton3 = Tk.Button(frame2, text='Start/Stop', command=self.sendStartToMCU)
        SendButton3.grid(row=2, columnspan=3, padx=5, pady=30)

    def sendKpToMCU(self):
        self.serialReference.sendSerialData('K' + self.entry1.get() + '%')     # '%' is our ending marker

    def sendSpdToMCU(self):
        self.serialReference.sendSerialData('S' + self.entry2.get() + '%')     # '%' is our ending marker

    def sendStartToMCU(self):
        self.serialReference.sendSerialData('R')    # only 1 letter so we dont need an ending marker

def main():
    # portName = 'COM5'
    portName = '/dev/ttyUSB0'
    baudRate = 38400
    maxPlotLength = 100     # number of points in x-axis of real time plot
    dataNumBytes = 4        # number of bytes of 1 data point
    numPlots = 3            # number of plots in 1 graph
    s = serialPlot(portName, baudRate, maxPlotLength, dataNumBytes, numPlots)   # initializes all required variables
    s.readSerialStart()                                               # starts background thread

    # plotting starts below
    pltInterval = 50    # Period at which the plot animation updates [ms]
    xmin = 0
    xmax = maxPlotLength
    ymin = -(0)
    ymax = 1.5
    fig = plt.figure(figsize=(10, 8))
    ax = plt.axes(xlim=(xmin, xmax), ylim=(float(ymin - (ymax - ymin) / 10), float(ymax + (ymax - ymin) / 10)))
    ax.set_title('Arduino Motor Control')
    ax.set_xlabel("Time")
    ax.set_ylabel("Voltage(V)")

    # put our plot onto Tkinter's GUI
    root = Tk.Tk()
    app = Window(fig, root, s)

    lineLabel = ['Desired', 'Actual', 'Error']
    style = ['r-', 'c-', 'b-']  # linestyles for the different plots
    timeText = ax.text(0.70, 0.95, '', transform=ax.transAxes)
    lines = []
    lineValueText = []
    for i in range(numPlots):
        lines.append(ax.plot([], [], style[i], label=lineLabel[i])[0])
        lineValueText.append(ax.text(0.70, 0.90-i*0.05, '', transform=ax.transAxes))
    anim = animation.FuncAnimation(fig, s.getSerialData, fargs=(lines, lineValueText, lineLabel, timeText), interval=pltInterval)    # fargs has to be a tuple

    plt.legend(loc="upper left")
    root.mainloop()   # use this instead of plt.show() since we are encapsulating everything in Tkinter

    s.close()


if __name__ == '__main__':
    main()