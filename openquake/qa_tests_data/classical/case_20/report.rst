Classical Hazard QA Test, Case 20
=================================

============================================== ========================
gem-tstation:/home/michele/ssd/calc_81066.hdf5 Thu Jan 26 14:29:25 2017
engine_version                                 2.3.0-gite807292        
hazardlib_version                              0.23.0-gite1ea7ea       
============================================== ========================

num_sites = 1, sitecol = 762 B

Parameters
----------
=============================== ===============================
calculation_mode                'classical'                    
number_of_logic_tree_samples    0                              
maximum_distance                {'Active Shallow Crust': 200.0}
investigation_time              1.0                            
ses_per_logic_tree_path         1                              
truncation_level                3.0                            
rupture_mesh_spacing            2.0                            
complex_fault_mesh_spacing      2.0                            
width_of_mfd_bin                1.0                            
area_source_discretization      10.0                           
ground_motion_correlation_model None                           
random_seed                     106                            
master_seed                     0                              
=============================== ===============================

Input files
-----------
======================= ============================================================
Name                    File                                                        
======================= ============================================================
gsim_logic_tree         `gsim_logic_tree.xml <gsim_logic_tree.xml>`_                
job_ini                 `job.ini <job.ini>`_                                        
source                  `source_model.xml <source_model.xml>`_                      
source_model_logic_tree `source_model_logic_tree.xml <source_model_logic_tree.xml>`_
======================= ============================================================

Composite source model
----------------------
========================= ====== ====================================== =============== ================
smlt_path                 weight source_model_file                      gsim_logic_tree num_realizations
========================= ====== ====================================== =============== ================
sm1_sg1_cog1_char_complex 0.070  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg1_cog1_char_plane   0.105  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg1_cog1_char_simple  0.175  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg1_cog2_char_complex 0.070  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg1_cog2_char_plane   0.105  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg1_cog2_char_simple  0.175  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg2_cog1_char_complex 0.030  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg2_cog1_char_plane   0.045  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg2_cog1_char_simple  0.075  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg2_cog2_char_complex 0.030  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg2_cog2_char_plane   0.045  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
sm1_sg2_cog2_char_simple  0.075  `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
========================= ====== ====================================== =============== ================

Required parameters per tectonic region type
--------------------------------------------
====== ================ ========= ========== ==========
grp_id gsims            distances siteparams ruptparams
====== ================ ========= ========== ==========
0      SadighEtAl1997() rrup      vs30       mag rake  
1      SadighEtAl1997() rrup      vs30       mag rake  
2      SadighEtAl1997() rrup      vs30       mag rake  
3      SadighEtAl1997() rrup      vs30       mag rake  
4      SadighEtAl1997() rrup      vs30       mag rake  
5      SadighEtAl1997() rrup      vs30       mag rake  
6      SadighEtAl1997() rrup      vs30       mag rake  
7      SadighEtAl1997() rrup      vs30       mag rake  
8      SadighEtAl1997() rrup      vs30       mag rake  
9      SadighEtAl1997() rrup      vs30       mag rake  
10     SadighEtAl1997() rrup      vs30       mag rake  
11     SadighEtAl1997() rrup      vs30       mag rake  
====== ================ ========= ========== ==========

Realizations per (TRT, GSIM)
----------------------------

::

  <RlzsAssoc(size=12, rlzs=12)
  0,SadighEtAl1997(): ['<0,sm1_sg1_cog1_char_complex~Sad1997,w=0.07000000029802322>']
  1,SadighEtAl1997(): ['<1,sm1_sg1_cog1_char_plane~Sad1997,w=0.10499999672174454>']
  2,SadighEtAl1997(): ['<2,sm1_sg1_cog1_char_simple~Sad1997,w=0.17499999701976776>']
  3,SadighEtAl1997(): ['<3,sm1_sg1_cog2_char_complex~Sad1997,w=0.07000000029802322>']
  4,SadighEtAl1997(): ['<4,sm1_sg1_cog2_char_plane~Sad1997,w=0.10499999672174454>']
  5,SadighEtAl1997(): ['<5,sm1_sg1_cog2_char_simple~Sad1997,w=0.17499999701976776>']
  6,SadighEtAl1997(): ['<6,sm1_sg2_cog1_char_complex~Sad1997,w=0.029999999329447746>']
  7,SadighEtAl1997(): ['<7,sm1_sg2_cog1_char_plane~Sad1997,w=0.04500000178813934>']
  8,SadighEtAl1997(): ['<8,sm1_sg2_cog1_char_simple~Sad1997,w=0.07500000298023224>']
  9,SadighEtAl1997(): ['<9,sm1_sg2_cog2_char_complex~Sad1997,w=0.029999999329447746>']
  10,SadighEtAl1997(): ['<10,sm1_sg2_cog2_char_plane~Sad1997,w=0.04500000178813934>']
  11,SadighEtAl1997(): ['<11,sm1_sg2_cog2_char_simple~Sad1997,w=0.07500000298023224>']>

Number of ruptures per tectonic region type
-------------------------------------------
================ ====== ==================== =========== ============ ============
source_model     grp_id trt                  num_sources eff_ruptures tot_ruptures
================ ====== ==================== =========== ============ ============
source_model.xml 0      Active Shallow Crust 3           86           86          
source_model.xml 1      Active Shallow Crust 3           86           86          
source_model.xml 2      Active Shallow Crust 3           86           86          
source_model.xml 3      Active Shallow Crust 3           119          119         
source_model.xml 4      Active Shallow Crust 3           119          119         
source_model.xml 5      Active Shallow Crust 3           119          119         
source_model.xml 6      Active Shallow Crust 3           88           88          
source_model.xml 7      Active Shallow Crust 3           88           88          
source_model.xml 8      Active Shallow Crust 3           88           88          
source_model.xml 9      Active Shallow Crust 3           121          121         
source_model.xml 10     Active Shallow Crust 3           121          121         
source_model.xml 11     Active Shallow Crust 3           121          121         
================ ====== ==================== =========== ============ ============

============= =====
#TRT models   12   
#sources      36   
#eff_ruptures 1,242
#tot_ruptures 1,242
#tot_weight   2,880
============= =====

Informational data
------------------
=========================================== ============
count_eff_ruptures_max_received_per_task    1,222       
count_eff_ruptures_num_tasks                18          
count_eff_ruptures_sent.gsims               1,638       
count_eff_ruptures_sent.monitor             18,000      
count_eff_ruptures_sent.sitecol             10,764      
count_eff_ruptures_sent.sources             101,914     
count_eff_ruptures_tot_received             21,996      
hazard.input_weight                         2,880       
hazard.n_imts                               1           
hazard.n_levels                             4           
hazard.n_realizations                       12          
hazard.n_sites                              1           
hazard.n_sources                            36          
hazard.output_weight                        48          
hostname                                    gem-tstation
require_epsilons                            False       
=========================================== ============

Slowest sources
---------------
====== ========= ========================= ============ ========= ========= =========
grp_id source_id source_class              num_ruptures calc_time num_sites num_split
====== ========= ========================= ============ ========= ========= =========
7      CHAR1     CharacteristicFaultSource 1            0.0       1         0        
9      SFLT1     SimpleFaultSource         58           0.0       1         0        
9      CHAR1     CharacteristicFaultSource 1            0.0       1         0        
0      COMFLT1   ComplexFaultSource        29           0.0       1         0        
7      COMFLT1   ComplexFaultSource        29           0.0       1         0        
0      CHAR1     CharacteristicFaultSource 1            0.0       1         0        
1      SFLT1     SimpleFaultSource         56           0.0       1         0        
4      CHAR1     CharacteristicFaultSource 1            0.0       1         0        
4      COMFLT1   ComplexFaultSource        62           0.0       1         0        
10     SFLT1     SimpleFaultSource         58           0.0       1         0        
11     SFLT1     SimpleFaultSource         58           0.0       1         0        
11     CHAR1     CharacteristicFaultSource 1            0.0       1         0        
5      SFLT1     SimpleFaultSource         56           0.0       1         0        
6      SFLT1     SimpleFaultSource         58           0.0       1         0        
8      SFLT1     SimpleFaultSource         58           0.0       1         0        
2      CHAR1     CharacteristicFaultSource 1            0.0       1         0        
2      SFLT1     SimpleFaultSource         56           0.0       1         0        
3      SFLT1     SimpleFaultSource         56           0.0       1         0        
3      CHAR1     CharacteristicFaultSource 1            0.0       1         0        
6      CHAR1     CharacteristicFaultSource 1            0.0       1         0        
====== ========= ========================= ============ ========= ========= =========

Computation times by source typology
------------------------------------
========================= ========= ======
source_class              calc_time counts
========================= ========= ======
CharacteristicFaultSource 0.0       12    
ComplexFaultSource        0.0       12    
SimpleFaultSource         0.0       12    
========================= ========= ======

Information about the tasks
---------------------------
================== ========= ========= ========= ===== =========
operation-duration mean      stddev    min       max   num_tasks
count_eff_ruptures 8.174E-04 1.261E-04 6.013E-04 0.001 18       
================== ========= ========= ========= ===== =========

Slowest operations
------------------
================================ ========= ========= ======
operation                        time_sec  memory_mb counts
================================ ========= ========= ======
reading composite source model   0.762     0.0       1     
filtering composite source model 0.043     0.0       1     
managing sources                 0.037     0.0       1     
split/filter heavy sources       0.022     0.0       6     
total count_eff_ruptures         0.015     0.0       18    
store source_info                6.955E-04 0.0       1     
aggregate curves                 2.358E-04 0.0       18    
reading site collection          3.719E-05 0.0       1     
saving probability maps          2.432E-05 0.0       1     
================================ ========= ========= ======