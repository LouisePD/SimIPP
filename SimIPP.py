# -*- coding:utf-8 -*-

import pandas as pd
import numpy as np
from pandas import merge, notnull, DataFrame, Series
import pdb


path = "C:\\TaxIPP-Life\\SimIPP\\"

# Partie 1 :définition des étapes et fonctions :
class Pension(object):
    def __init__(self):
            self.simul = None
            self.survie = None
            self.survieF = None
            self.survieH = None
            self.beta = 0.97
            self.kappa = 1.25
            self.gamma = 0.6
            
    def load(self):
        simul = pd.read_csv(path + 'simul.csv', sep=',')                 
        simul.columns = ['index', 'id', 'date', 'time', 'salaire', 'pension', 'agem', 'sexe' ]
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
        
    def calculate_pond_time(self):
        ''' Associe les vecteurs de pondérations'''
        simul =  self.simul #[self.simul['id'].isin([3,9,17920,18522,41302])]
        print "Nombre de lignes dans la base : "  + str(len(simul))
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
            length = (group_calcul['date_max'] - group_calcul['date_min']).sum() + len(group_calcul)
            group_calcul.index = range(0, len(group_calcul))
            print "Nombre de groupes pour calcul des vecteurs d'actualisation : " + str(len(group_calcul))
            
            # Attribution de son numéro de groupe à chaque individu
            info = info[['id', 'groupe']]
            #info.to_csv('infogr.csv')
            return group_calcul, info, length

        def _pond_vie(ti, ageti,  tf):
            ''' renvoie une matrice de taille (tf - ti + 1 )^2
            contenant les vecteurs de pondérations poour tous les ti<=t<= tf 
            t (= indice de la ligne est reporté dans la première colonne)'''
            esp = np.zeros((tf-ti+1,tf-ti+1))
            for t in range(ti, tf+1):
                # Vecteur de pondération par espérance de vie : 
                t_ann = int(round(t/12))
                aget = ageti + (t - ti)
                esp_t = survie.loc[aget : ageti + (tf - ti), t_ann] 
                act = (np.ones(len(esp_t))* beta)**range(len(esp_t))
                esp_i = (act * esp_t) / survie.loc[aget, t_ann]
                esp[t-ti,t-ti:] = esp_i
            #esp = pd.DataFrame(esp)
            #esp.to_csv('testesp.csv')
            return esp
        
        def _pond_to_groupe(info_gr, long_esp):
            ''' Attribue les vecteurs de pondérations à chacun des groupes (ident_groupe dans 1er colonne)
            renvoie une matrice (23485,138) : 1 ligne par groupe et par date'''
            nb_groupe = len(info_gr)
            esp = np.zeros((long_esp,138))
            index_ini = 0
            for i in range(nb_groupe): 
                # Caractéristiques du groupes
                ti, tf, agei =  info_gr.loc[i,['date_min','date_max' ,'agem_min']]
                esp_i = _pond_vie(ti,agei, tf)
                dur_group = esp_i.shape[1] # = (tf - ti + 1) 
                esp[index_ini : index_ini + dur_group, 0] = i
                esp[index_ini : index_ini +dur_group, 1:dur_group + 1] = esp_i
                index_ini = index_ini + dur_group
            #esp = pd.DataFrame(esp)
            #esp.to_csv('testdeesp.csv')
            return esp
        
        # Appel des fonctions
        info_gr, info, long_esp = _info_ind(ident,simul)
        esp = _pond_to_groupe(info_gr, long_esp)
        self.esp = esp
        self.info = info
        
    def pension_calcul(self):
        gamma = self.gamma
        kappa = self.kappa
    
        def _income_vectors(data):
            ''' Cette fonction retourne une matrice dont les colonnes sont les vecteurs de revenus
            correpondant aux différents horizons de retraite (prend sa retraite en t=r)'''
            nb_period = len(data)
            # Rq : passage sous numpy pour faciliter le calcul + réindexation à partir de zéro
            # correspondances :  (salaire,0 ); (pension, 1); 
            income = np.zeros((nb_period,nb_period))
            for r in range(0,nb_period ):
                # Vecteur des revenus
                income[r,:r] = data[:r,0]
                income[r,r:] = kappa*data[r,1]
            income = income**gamma
            income = income.transpose()
            #income = pd.DataFrame(income)
            #income.to_csv('income_alexis.csv')
            return income
            
        def _calcul_cout_opt(income, esp):
            ''' Cette fonction renvoie le vecteur des Vt(r*) - Vt(t)'''
            esp = esp[:,1:len(income)+1]
            vec = np.dot(esp, income)
            # Cette matrice diagonale contient toutes les valeurs Vt(r) 
            # indice de ligne : t, indice de colonne : r 
            vec = np.triu(vec)
            # On sauvegarde les valeurs Vt(t) qui apparaissent sur le diagonale
            V_tt = np.diag(vec)
            vec_max = np.amax(vec, axis=1) -  V_tt
            # vec = pd.DataFrame(vec_max)
            # vec.to_csv('testvec.csv')
            return vec_max
       
        def _last_calculate(simul, info, esp) :
            simul = simul.sort(['id','time'])
            list_id = np.unique(simul['id'].tolist())
            result = pd.DataFrame(index=list_id, columns=range(137))
            simul = np.array(simul[['salaire', 'pension','id']])
            # TODO: faire une boucle d'abord sur les sous groupes
            # puis chercher les i dans chaque sous-groupe
            for ident_group, indivs in info.groupby('groupe'):
                esp_group = esp[esp[:,0] == ident_group,:]
                for i in indivs['id']:
                    perso = simul[simul[:,2]==i,:]
                    income = _income_vectors(perso)
                    vect = _calcul_cout_opt(income, esp_group)
                    result.loc[i,0:len(vect)-1] = vect
            return result
                
        # Appelle des fonctions et calcul final
        simul = self.simul
        esp = self.esp
        info = self.info
        result =  _last_calculate(simul,info,esp)
        result.to_csv('testdusimul.csv')
        
# Partie 2 : Appelle du code
import time
start_t = time.time()
data = Pension()
data.load()  
data.format()
int_time = time.time()
print "Importation terminée"
data.calculate_pond_time()
after_pond = time.time()
print "Calculs préliminaires terminés"
data.pension_calcul()
end_t = time.time()
print ("Voilà, c'est fini! Temps de calcul : " + str(end_t - start_t)  + 
    "s dont " + str(int_time - start_t)  + "s d'importation et " +
      str(after_pond - int_time)  + "s pour calculate_pond et " +
      str(end_t - after_pond)  + "s pour pension_calcul ")
     
#import cProfile
#command = 'data.pension_calcul()'
#cProfile.runctx( command, globals(), locals(), filename="modif2")
 