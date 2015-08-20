Classical PSHA QA test with sites_csv
=====================================

Parameters
----------
============================ =========
calculation_mode             classical
number_of_logic_tree_samples 0        
maximum_distance             200.0    
investigation_time           50.0     
ses_per_logic_tree_path      1        
truncation_level             3.0      
rupture_mesh_spacing         2.0      
complex_fault_mesh_spacing   2.0      
width_of_mfd_bin             0.1      
area_source_discretization   10.0     
random_seed                  23       
master_seed                  0        
concurrent_tasks             32       
============================ =========

Input files
-----------
======================= ============================================================
Name                    File                                                        
======================= ============================================================
gsim_logic_tree         `gmpe_logic_tree.xml <gmpe_logic_tree.xml>`_                
job_ini                 `job.ini <job.ini>`_                                        
sites                   `qa_sites.csv <qa_sites.csv>`_                              
source                  `simple_fault.xml <simple_fault.xml>`_                      
source_model_logic_tree `source_model_logic_tree.xml <source_model_logic_tree.xml>`_
======================= ============================================================

Composite source model
----------------------
============ ====== ====================================== =============== ================ ===========
smlt_path    weight source_model_file                      gsim_logic_tree num_realizations num_sources
============ ====== ====================================== =============== ================ ===========
simple_fault 1.00   `simple_fault.xml <simple_fault.xml>`_ simple(2)       2/2              15         
============ ====== ====================================== =============== ================ ===========

Realizations per (TRT, GSIM)
----------------------------

::

  <RlzsAssoc(2)
  0,AbrahamsonSilva2008: ['<0,simple_fault,AbrahamsonSilva2008,w=0.5>']
  0,CampbellBozorgnia2008: ['<1,simple_fault,CampbellBozorgnia2008,w=0.5>']>

Expected data transfer for the sources
--------------------------------------
================================== ========
Number of tasks to generate        13      
Estimated sources to send          27.07 KB
Estimated hazard curves to receive 26 KB   
================================== ========