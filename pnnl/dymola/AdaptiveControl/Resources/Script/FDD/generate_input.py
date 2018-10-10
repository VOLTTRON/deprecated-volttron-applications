Load_Max=1800

Load_Min=200

Load_interval=100


T_Max=30

T_Min=15

T_interval=1


f=open('Signal.txt','w')

f.writelines('#1'+'\n')

n=int((T_Max-T_Min)/T_interval*(Load_Max-Load_Min)/Load_interval)


f.writelines('double tab1('+str(n)+',3)   # comment line'+'\n')

time=0
for i in range(Load_Min,Load_Max,Load_interval):
    for j in range(T_Min,T_Max,T_interval):
      f.writelines('           '+str(time)+'          '+str(i)+'          '+str(j+273.15)+'\n')
      time=time+15*60
	  
f.close()