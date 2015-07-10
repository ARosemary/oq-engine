Classical Hazard QA Test, Case 7
================================

Parameters
----------
============================ =========
calculation_mode             classical
number_of_logic_tree_samples 0        
maximum_distance             200.0    
investigation_time           1.0      
ses_per_logic_tree_path      1        
truncation_level             0.0      
rupture_mesh_spacing         0.01     
complex_fault_mesh_spacing   0.01     
width_of_mfd_bin             1.0      
area_source_discretization   10.0     
random_seed                  1066     
master_seed                  0        
============================ =========

Input files
-----------
======================= ============================================================
Name                    File                                                        
======================= ============================================================
gsim_logic_tree         `gsim_logic_tree.xml <gsim_logic_tree.xml>`_                
job_ini                 `job.ini <job.ini>`_                                        
source                  `source_model_1.xml <source_model_1.xml>`_                  
source                  `source_model_2.xml <source_model_2.xml>`_                  
source_model_logic_tree `source_model_logic_tree.xml <source_model_logic_tree.xml>`_
======================= ============================================================

Composite source model
----------------------
========= ====== ========================================== ======== =============== ================ ===========
smlt_path weight source_model_file                          num_trts gsim_logic_tree num_realizations num_sources
========= ====== ========================================== ======== =============== ================ ===========
b1        0.70   `source_model_1.xml <source_model_1.xml>`_ 1        trivial(1)      1/1              2          
b2        0.30   `source_model_2.xml <source_model_2.xml>`_ 1        trivial(1)      1/1              1          
========= ====== ========================================== ======== =============== ================ ===========

Realizations per (TRT, GSIM)
----------------------------

::

  <RlzsAssoc(2)
  0,SadighEtAl1997: ['<0,b1,b1,w=0.7>']
  1,SadighEtAl1997: ['<1,b2,b1,w=0.3>']>