import ctypes
import time

_relayIO = ctypes.CDLL('relayIO.so')


def relaySetup():

    _relayIO.relaySetup()

def relaySet(R):

    _relayIO.relaySet(ctypes.c_int(R))

def relayClear(R):

    _relayIO.relayClear(ctypes.c_int(R))

def relayRead(R):

    mode = _relayIO.relayRead(ctypes.c_int(R))

    return mode

def test():

        for i in range(0,6):
            tmp = relayRead(i+1)
            print(str(tmp))
            time.sleep(0.5)

    	relaySetup()
    	time.sleep(0.5)

    	for i in range(0,6):
                relaySet(i+1)
                time.sleep(0.5)

	for i in range(0,6):
                tmp = relayRead(i+1)
                print(str(tmp))
                time.sleep(0.5)
	

    	for i in range(0,6):
                relayClear(i+1)
                time.sleep(0.5)

#if __name__ == '__main__':

 #   test()


