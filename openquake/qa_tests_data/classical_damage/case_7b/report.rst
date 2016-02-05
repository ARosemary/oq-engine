Classical PSHA-Based Hazard
===========================

num_sites = 7, sitecol = 960 B

Parameters
----------
============================ ================
calculation_mode             classical_damage
number_of_logic_tree_samples 0               
maximum_distance             200.0           
investigation_time           50.0            
ses_per_logic_tree_path      1               
truncation_level             3.0             
rupture_mesh_spacing         1.0             
complex_fault_mesh_spacing   1.0             
width_of_mfd_bin             0.1             
area_source_discretization   20.0            
random_seed                  42              
master_seed                  0               
concurrent_tasks             16              
sites_per_tile               1000            
============================ ================

Input files
-----------
======================= ============================================================
Name                    File                                                        
======================= ============================================================
exposure                `exposure_model.xml <exposure_model.xml>`_                  
gsim_logic_tree         `gmpe_logic_tree.xml <gmpe_logic_tree.xml>`_                
job_ini                 `job_haz.ini <job_haz.ini>`_                                
source                  `source_model.xml <source_model.xml>`_                      
source_model_logic_tree `source_model_logic_tree.xml <source_model_logic_tree.xml>`_
structural_fragility    `fragility_model.xml <fragility_model.xml>`_                
======================= ============================================================

Composite source model
----------------------
========= ====== ====================================== =============== ================
smlt_path weight source_model_file                      gsim_logic_tree num_realizations
========= ====== ====================================== =============== ================
b1        1.00   `source_model.xml <source_model.xml>`_ trivial(1)      1/1             
========= ====== ====================================== =============== ================

Required parameters per tectonic region type
--------------------------------------------
====== ============== ========= ========== ==========
trt_id gsims          distances siteparams ruptparams
====== ============== ========= ========== ==========
0      SadighEtAl1997 rrup      vs30       rake mag  
====== ============== ========= ========== ==========

Realizations per (TRT, GSIM)
----------------------------

::

  <RlzsAssoc(1)
  0,SadighEtAl1997: ['<0,b1,b1,w=1.0>']>

Number of ruptures per tectonic region type
-------------------------------------------
================ ====== ==================== =========== ============ ======
source_model     trt_id trt                  num_sources eff_ruptures weight
================ ====== ==================== =========== ============ ======
source_model.xml 0      Active Shallow Crust 1           1694         1694.0
================ ====== ==================== =========== ============ ======

Expected data transfer for the sources
--------------------------------------
=========================== ========
Number of tasks to generate 13      
Sent data                   85.63 KB
=========================== ========

Exposure model
--------------
=========== =
#assets     7
#taxonomies 3
=========== =

======== =======
Taxonomy #Assets
======== =======
Concrete 2      
Steel    2      
Wood     3      
======== =======

Slowest sources
---------------
============ ========= ================= ====== ========= =========== ========== =========
trt_model_id source_id source_class      weight split_num filter_time split_time calc_time
============ ========= ================= ====== ========= =========== ========== =========
0            1         SimpleFaultSource 1694.0 15        0.00210404  0.11682    0.0      
============ ========= ================= ====== ========= =========== ========== =========