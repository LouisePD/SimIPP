# -*- coding:utf-8 -*-

import pandas as pd
import numpy as np
from pandas import merge, notnull, DataFrame, Series
import pdb


path = "C:\\TaxIPP-Life\\SimIPP\\"

# Partie 1 :définition des étapes et fonctions :
class Pension(object):
    def __init__(self):
            self.simul2 = None
            self.survieF = None
            self.survieH = None
            self.beta = 0.97
            self.kappa = 1.25
            self.gamma = 0.6
            
            
    def load(self): 
        simul2 = pd.read_csv(path + 'simul2.csv', sep=',')                       
        simul2.columns = ['index', 'id', 'date', 'time', 'salaire', 'pension', 'agem', 'sexe' ]
        survieF = pd.read_csv(path + 'survieF.csv', sep=',', dtype = np.float)
        survieF = np.round(survieF,4)
        survieH = pd.read_csv(path + 'survieH.csv', sep=',')
        survieH = np.round(survieH,4)
        self.simul = simul2
        self.survieH = survieH
        self.survieF = survieF

    def format(self):
        simul =  self.simul
        survieH = self.survieH 
        survieF = self.survieF
        def _date_clean():
            ''' Cette fonction permet de mettre 'date' au format : yyyymm 
            + 'time' comme des entiers successifs '''
            month = ((simul['date'] %1) * 12 + 1).round().astype(int)
            year = ((simul['date'] // 1) * 100).astype(int)
            simul['date'] = year + month
            simul['time'] = (simul['time']/30).astype(int)
            self.min_time = simul['time'].min()
            self.max_time = simul['time'].max()
            print 'La période détude de léchantillon est de ' + str(simul['date'].min()) + ' à '+ str(simul['date'].max()) 
            print ' Ce qui correspond, dans le format time, aux valeurs de ' + str(self.min_time)  + ' à '+ str(self.max_time) 
            
        def _index_survie(survie, min_time, max_time):
            # -1 : car première colonne lue = index
            # year = 1900 <-> time = -60
            survie.columns = range(-60 -1,  -60 - 1 + len(survie.columns) )
            survie = survie.set_index(-60 - 1)
            survie = survie.loc[: , min_time : max_time]
            return survie
            
        # Reformatages effectifs
        simul['agem'] = simul['agem'].astype(int)       
        for var in ['pension', 'salaire'] :
            simul[var] = simul[var].round(2) 
        _date_clean()
        
        # Suppression les variables inutiles
        simul = simul.drop(['index'], axis=1)
        
        # Sauvegarde des changemets effectués
        self.simul = simul
        self.survieH = _index_survie(survieH, self.min_time/12, self.max_time/12)
        self.survieF = _index_survie(survieF, self.min_time/12, self.max_time/12)
        #simul.to_csv('test0.csv')
        #self.survieF.to_csv('testsurvie.csv')
        
    def pension_ini(self):
        simul =  self.simul
        survieH = self.survieH 
        survieF = self.survieF
        
        # Liste des identifiants de la base (ident.index) + leur sexe (ident)
        ident = simul.drop_duplicates(['id'])[['id', 'sexe']]
        ident = ident.set_index('id')
        ident = ident['sexe']
        print "Nombre d'individus dans la base : " + str(len(ident))
        
        
        def _info_ind(ident):
            info = pd.DataFrame(simul.groupby('id').time.min(), index = ident.index, columns = ['date_min'])
            info = info.join(simul.groupby('id').time.max())  
            info = info.join(simul.groupby('id').agem.min())
            info.columns = ['date_min', 'date_max', 'agem_min']
            info['id'] = info.index
            info = info.sort(['date_min','agem_min', 'date_max'])
            to_drop = False
            for var in ['date_min','agem_min', 'date_max']:
                    to_drop = to_drop | (info[var].shift(1) != info[var])
            info['groupe'] = (to_drop).astype(int).cumsum() - 1
            info['groupe'] = info['groupe'].astype(int)
            group_calcul = info.drop_duplicates(['groupe'])
            group_calcul.index = range(0, len(group_calcul))
            info.to_csv('info.csv')
            print "Nombre de groupes pour calcul : " + str(len(group_calcul))
            self.info_gr = group_calcul 
            self.info = info
        
        def _gamma_by_group():
            ''' Le but de cette fonction est de calculer les Gamma(t, tf, agei) avec t>=ti
            pour chaque triplet de valeur (ti,tf,agei) contenu dans info_gr '''
            info = self.info_gr
            simul = self.simul
            beta = self.beta
            survie = self.survieH
            # Liste de stockage des valeurs calculées  
            V = []
            for i in range(len(info)) : # [3,9,24]
                V_i = []
                # Caractéristiques du groupes
                ti, tf, agei =  info.iloc[i,0:3]
                for t in range(ti, tf + 1 ):
                    V_it = 0
                    t_ann = int(round(t/12))
                    for k in range(0, tf - t +1):
                        V_it = V_it + survie.loc[agei + k, t_ann] * (beta**k)
                    V_i = V_i + [V_it]
                V = V + [V_i] 
            V = pd.DataFrame(V)
            return V
        
        def _retraite_tt():
            info = self.info
            simul =self.simul
            
            # 1ere étape - on ajoute les gammatt
            print "Nombre d'individus dans la base : " + str(len(ident))
            to_add = info.drop(['groupe'], axis = 1)
            to_add = to_add.set_index(['id','date_min', 'date_max', 'agem_min']).stack().reset_index()
            to_add.columns = ['id','date_min', 'date_max', 'agem_min', 'period', 'V']
            to_add = to_add.sort(['id', 'period'])
            to_add.index = range(0,len(to_add))
            to_add.to_csv('testduadd.csv')
            print len(to_add)
            simul = simul.sort(['id', 'agem'])
            simul.index = range(0,len(simul))
            simul = merge(to_add, simul, left_on = to_add.index, right_on = simul.index, how = 'outer')
            
            # 2eme étape - on calcul les Vtt

            # Enregistrement
            self.simul = simul

        # Changements et sauvegardes
        _info_ind(ident)
        V = _gamma_by_group()
        self.info = merge(self.info, V, left_on = 'groupe', right_on = V.index, left_index = True, how ='outer')
        #self.info.to_csv('merge.csv')
        _retraite_tt()

            
# Partie 2 : Appelle du code
import time
start_t = time.time()
data = Pension()
data.load()  
data.format()
data.pension_ini()
print "Voilà, c'est fini! Temps de calcul : " + str(time.time() - start_t) + "s"  