import json
import csv
import re
import os
import shutil
import numpy as np

print("Start recording Qh and hvac values based on pre-run gld simulation results")

inputFolderName = "/home/yingying/Documents/HEMS_Demand_response_test_case/TestCase/output/"

# parameters to be written into config files
# Subscription to FNCS_Bridge simulation_end message
hvacHouses = {}
QhHouses = {}

# Qh data:
data = []
houseName = ""
readName = False
with open(inputFolderName + '/' + 'AC_WH_data_Qh.csv') as fobj:
#         print (file)
    for line in fobj:
        row = line.split(',')
        if len(row) > 2:
            if readName == False:
                houseName = row[1:]
                readName = True
            else:
                data.append([float(i) for i in row[1:]])
    dataArray = np.array(data)
    avg = np.true_divide(dataArray.sum(0),(dataArray!=0).sum(0))
    for i in range(len(houseName)):
        name = houseName[i].split(':')[0]
        QhHouses[name] = avg[i]

# hvac data
data = []
houseName = ""
readName = False
with open(inputFolderName + '/' + 'AC_WH_data_hvac.csv') as fobj:
    for line in fobj:
        row = line.split(',')
        if len(row) > 2:
            if readName == False:
                houseName = row[1:]
                readName = True
            else:
                data.append([float(i) for i in row[1:]])
    dataArray = np.array(data)
    avg = np.true_divide(dataArray.sum(0),(dataArray!=0).sum(0))
    for i in range(len(houseName)):
        name = houseName[i].split(':')[0]
        hvacHouses[name] = avg[i]

print('finish recording Qh and hvac values based on pre-run gld simulation results')  
print hvacHouses
print QhHouses
#     with open(inputQhFolderName + '/' + file, 'rb') as f:
#         
#         reader = csv.reader(f)
#         Qh_list = list(reader)
#         Qh_house_name = Qh_list[7][1:]
#         Qh_val = Qh_list[8:]
#         l = np.array(Qh_val)[1:,:]
#         ans= l.sum(1)/(l != 0).sum(1)
#         ans=np.apply_along_axis(lambda v: np.mean(l[np.nonzero(v)]), 0, l)
#         average = l[np.nonzero(l)].mean()
        
        

