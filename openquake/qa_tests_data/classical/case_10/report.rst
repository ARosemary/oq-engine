Classical Hazard QA Test, Case 10
=================================

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
width_of_mfd_bin             0.001    
area_source_discretization   10.0     
random_seed                  1066     
master_seed                  0        
concurrent_tasks             32       
============================ =========

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
========= ====== ====================================== =============== ================ ===========
smlt_path weight source_model_file                      gsim_logic_tree num_realizations num_sources
========= ====== ====================================== =============== ================ ===========
b1_b2     0.500  `source_model.xml <source_model.xml>`_ trivial(1)      1/1              1          
b1_b3     0.500  `source_model.xml <source_model.xml>`_ trivial(1)      1/1              1          
========= ====== ====================================== =============== ================ ===========

Realizations per (TRT, GSIM)
----------------------------

::

  <RlzsAssoc(2)
  0,SadighEtAl1997: ['<0,b1_b2,b1,w=0.5>']
  1,SadighEtAl1997: ['<1,b1_b3,b1,w=0.5>']>

Expected data transfer for the sources
--------------------------------------
================================= =======
Number of tasks to be generated   2      
Estimated data to be sent forward 3.73 KB
Estimated data to be sent back    64 B   
================================= =======