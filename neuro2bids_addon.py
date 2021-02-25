#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 17 11:51:51 2021

@author: lh265624
"""

import os

#For each file in the bids data set:
for root, dirs, files in os.walk("/home/lh265624/Desktop/bids_dataset/"):
   for fil in files :
       #if the name contains sub (not the case for readme files for example)
       if fil.find("sub") is not -1:
           #memorize the original name of the file 
           originalname = fil
           #delete the added _ph which occurs for phase maps during the conversion from DICOM to NIFTI
           if fil.find("_ph") is not -1:
               if fil.find("part") is not -1:
                   fil = fil.replace("part","part-phase")
                   fil = fil.replace("_ph","")
               else:
                   fil = fil.replace('_ph.','phase.')
           elif fil.find("part") is not -1:
               fil = fil.replace("part-label","part-mag")
           elif fil.find("__") is not -1:
               fil = fil.replace("__","_magnitude_")
           elif fil.find("_.") is not -1:
               fil = fil.replace("_.","_magnitude.")
           if fil.find("a.") is not -1:
               fil=fil.replace("a.",".")
           #Search for and delete the added _e in case of several echoh times
           fila=fil.replace('_echo','')
           ind = fila.find("_e")
           #Save the index of the TE 
           if ind is not -1:
               ind += 5
               if fil[ind+3] is not ".":
                   num = fil[ind+2]+fil[ind+3]
               else:
                   num = fil[ind+2]
               #Delete the _e and add the index to the file name 
               et = "_e"+num
               fil = fil.replace(et,'')
               fil = fil.replace('echo-num', 'echo-'+num)
           #Determine the original and final names of the files in their directories
           sub = fil[4]+fil[5]
           ses = fil[11]+fil[12]
           #Define in which folder each file is depending on the suffix
           if fil.find("magnitude.") is not -1 or fil.find("phase.") is not -1 or fil.find("B1map.") is not -1:
               fich = 'fmap'
           elif fil.find("dwi") is not -1:
               fich = 'dwi'
           else:
               fich = 'anat'
           direc = '/home/lh265624/Desktop/bids_dataset/sub-' + sub +'/ses-'+ses+'/'+fich+'/'+originalname
           newname = '/home/lh265624/Desktop/bids_dataset/sub-' + sub +'/ses-'+ses+'/'+fich+'/'+fil
           #Rename the files 
           os.rename(direc,newname)
       
       
           