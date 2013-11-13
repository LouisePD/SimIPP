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
        simul = pd.read_csv(path + 'simul.csv', sep=',')                      
        simul.columns = ['index', 'id', 'date', 'time', 'salaire', 'pension', 'agem', 'sexe' ]
        #simul = np.round(simul,7)
        survieF = pd.read_csv(path + 'survieF.csv', sep=',', dtype = np.float)
        survieF = np.round(survieF,4)
        survieH = pd.read_csv(path + 'survieH.csv', sep=',')
        survieH = np.round(survieH,4)
        self.simul = simul
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
            simul['time'] = (simul['time']/30).astype(int) + 60 * 12 # référence = 190001 
            simul['time'] = simul['time'].astype(int)  
            min_time = simul['time'].min()
            max_time = simul['time'].max()
            print 'La période détude de léchantillon est de ' + str(simul['date'].min()) + ' à '+ str(simul['date'].max()) 
            print ' Ce qui correspond, dans le format time, aux valeurs de ' + str(min_time)  + ' à '+ str(max_time) 
            
        def _index_survie(survie):
            # -1 : car première colonne lue = index
            # year = 1900 <-> time = 0
            survie.columns = range(-1, len(survie.columns) -1 )
            survie = survie.set_index(-1)
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
        self.survieH = _index_survie(survieH)
        self.survieF = _index_survie(survieF)
        
    def pension_ini(self):
        simul =  self.simul #[self.simul['id']==3]
        print "Nombre de ligne dans la base : "  + str(len(simul))
        survie = self.survieH 
        survieF = self.survieF
        beta = self.beta
        
        # Liste des identifiants de la base (ident.index) + leur sexe (ident)
        ident = simul.drop_duplicates(['id'])[['id', 'sexe']]
        ident = ident.set_index('id')
        ident = ident['sexe']
        print "Nombre d'individus dans la base : " + str(len(ident))
        
        def _info_ind(ident, simul):
            ''' Cette fonction permet de grouper les individus par (tmin, tmax, age(tmin))
            Ces triplets déterminent les vecteurs de pondération '''
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

            # Pour le calcul par groupe
            group_calcul = info.drop_duplicates(['groupe'])
            group_calcul.index = range(0, len(group_calcul))
            print "Nombre de groupes pour calcul des vecteurs d'actualisation : " + str(len(group_calcul))
            
            # Attribution de son numéro de groupe à chaque individu
            info = info[['id', 'groupe']]
            self.info = info
            #info.to_csv('infogr.csv')
            simul = merge(simul, info, on = 'id')
            return group_calcul, simul 

            
        def _pond_vie(ti, ageti,  tf):
            ''' renvoie une matrice de taille (tf - ti + 1 )^2
            contenant les vecteurs de pondérations poour tous les ti<=t<= tf '''
            esp = np.zeros((2,tf - ti +2))
            for t in range(ti, tf+1):
                esp_resid = np.zeros((t-ti))
                # Vecteur de pondération par espérance de vie : 
                t_ann = int(round(t/12))
                aget = ageti + (t - ti)
                esp_t = survie.loc[aget : ageti + (tf - ti), t_ann]
                act = (np.ones(len(esp_t))* beta)**range(len(esp_t))
                esp_t = act * esp_t / survie.loc[aget, t_ann]
                esp_t = np.array(esp_t).round(2)
                esp_t = np.concatenate([[t], esp_resid, esp_t])
                esp = np.concatenate([esp, [esp_t]], axis=0)
            esp = np.delete(esp, (0,1), axis=0)
            esp = pd.DataFrame(esp)
            return esp

        def _pond_to_groupe(info):
            ''' Attribue les vecteurs de pondérations à chacun des groupes '''
            nb_groupe = len(info)
            esp = []
            for i in range(nb_groupe): 
                # Caractéristiques du groupes
                ti, tf, agei =  info.loc[i,['date_min','date_max' ,'agem_min']]
                esp_i = _pond_vie(ti,agei, tf)
                esp = esp + [esp_i]
            esp = pd.concat(esp, keys = range(nb_groupe), names=['groupe'])
            esp['groupe'] = esp.index.get_level_values('groupe')
            esp = esp.rename(columns = {0:'time'})
            return esp
        
        # Appel des fonctions
        info_gr, simul = _info_ind(ident,simul)
        
        esp = _pond_to_groupe(info_gr)
        #esp.to_csv('testesp.csv')
        simul = merge(simul, esp, on= ['groupe', 'time'])
        self.simul = simul

    def pension_calcul(self):
        gamma = self.gamma
        kappa = self.kappa
    
        def _income_vectors(simul):
            ''' Cette fonction retourne une liste de vecteurs de revenus
            correpondant aux différents horizons de retraite (prend sa retraite en t=r)'''
            nb_period = len(simul)
            simul.index = range(nb_period)
            income = [np.array([(kappa * simul.loc[0,'pension'])**gamma]*(nb_period))]
            for r in range(1,nb_period ):
                # Vecteur des revenus
                sal = simul.loc[:r-1, 'salaire']
                pens = [kappa * simul.loc[r,'pension']] * (nb_period - r)
                income_r = np.concatenate([sal, pens])** gamma
                # Listes contenant les vecteurs de revenus lors de départ à la retaite en r
                income += [income_r]
            income = np.concatenate([income])
            income = income.transpose()
            income = pd.DataFrame(income)
            #income.to_csv('income.csv')
            return income
            
        def _calcul_cout_opt(income, simul):
            ''' Cette fonction renvoie le vecteur des Vt(r*) - Vt(t)'''
            esp = simul.loc[:,1 :len(simul)]
            vec = np.dot(esp, income)
            # Cette matrice diagonale contient toutes les valeurs Vt(r) 
            # indice de ligne : t, indice de colonne : r 
            vec = np.triu(vec)
            # On sauvegarde les valeurs Vt(t) qui apparaissent sur le diagonale
            V_tt = np.diag(vec)
            vec_max = np.amax(vec, axis=1) -  V_tt
            vec = pd.DataFrame(vec_max)
            #vec.to_csv('testvec.csv')
            return vec_max
       
        def _last_calculate(simul) :
           simul = simul.sort(['id','time'])
           list_id = simul['id'].drop_duplicates()
           for i in list_id:
                group = simul.loc[simul['id']==i,:]
                income = _income_vectors(group)
                vec_i = _calcul_cout_opt(income, group)
                #vec = vec + [vec_i]
                simul.loc[simul['id']==i, 'OVt'] = vec_i
           simul = simul.drop(range(1,60), axis = 1)
           return simul
                
        # Appelle des fonctions et calcul final
        simul = self.simul
        simul['OVt'] = -1
        simul = _last_calculate(simul)
        simul.to_csv('testdusimul.csv')
        
        '''
        simul = simul.sort(['id','time'])
        for group in simul.groupby('id') : 
            grouptest = np.array(group)
            
            income = map(_income_vectors,group)
            vec = _calcul_Vtr_opt(income, group)
            simul['OVt'] = vec
       '''

# Partie 2 : Appelle du code
import time
start_t = time.time()
data = Pension()
data.load()  
data.format()
data.pension_ini()
data.pension_calcul()
print "Voilà, c'est fini! Temps de calcul : " + str(time.time() - start_t)  + "s"  