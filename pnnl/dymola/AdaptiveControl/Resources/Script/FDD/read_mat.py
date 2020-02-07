from buildingspy.io.outputfile import Reader
import pandas as pd
import sys


def integration(x,y):
    ine=0
    for i in range(1,len(x)):
	       if x[i]-x[0]>3600*24:	       
	                ine=ine+(x[i]-x[i-1])*y[i-1]
    return ine

def sample(x,y,name):
    new_x=[]
    lenx=int((x[len(x)-1]-x[0])/60)
    for i in range(lenx):
	      new_x.append(x[0]+i*60)
    table=pd.DataFrame()
    table['time']=new_x
    for i in range(len(x)):
	      x[i]=int(x[i])
    table2=pd.DataFrame()
    table2['time']=x	
    table2[name]=y
    table2=table2.drop_duplicates(['time'])
    table=table.merge(table2,how='left')	


    return table	

baseline = '0'	
season = 'summer1'
#ofr1=Reader('Airflow_Network_baseline'+baseline+ '_'+season, "dymola")
ofr1=Reader('AHU', "dymola")

data_list=pd.read_csv('data_list_FDD.csv',header=None, names=['id','name'])

print data_list

index=1
for i in range(len(data_list)):
          
         (time, temp) = ofr1.values(data_list['id'].iloc[i].replace('\n',''))
         tab=sample(time, temp,data_list['name'].iloc[i])
         if index==1:
		     table1=tab
         else:
		     table1=table1.merge(tab,how='inner')
         index=index+1
             		     
table1=table1[24*60:]		 
table1.dropna(how='any')          
table1.to_csv('FDD.csv')



