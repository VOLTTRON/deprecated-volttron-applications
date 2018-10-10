import os

sum=0
for root, directories, filenames in os.walk('.'):
     for filename in filenames: 
             f=open(os.path.join(root,filename),'r')
             r=f.readlines()
             f.close()
             if len(r)>0:
                    for i in range(len(r)):
					               if r[i].find('Modelica_StateGraph2')!=-1:
								                                           print os.path.join(root,filename
