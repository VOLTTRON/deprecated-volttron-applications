import os

sum=0
for root, directories, filenames in os.walk('.'):
     for filename in filenames: 
             f=open(os.path.join(root,filename),'r')
             r=f.readlines()
             f.close()
             if len(r)>0:
                    r[0]=r[0].replace('within AdaptiveControl.PNNL_building_system.Buildings','within AdaptiveControl.PNNL_Buildings.Buildings')
             					
                    f=open(os.path.join(root,filename),'w')
                    for i in range(len(r)):
					               f.writelines(r[i])
                    f.close()