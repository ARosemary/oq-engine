We are often asked to recommend hardware configurations for servers and clusters to run the OpenQuake engine.  Obviously this depends very much on the calculations one wishes to perform and the available budget, but here we attempt to provide some general advice, please remember "your milage may vary".

Please note that currently **Ubuntu 12.04 LTS** (Precise Pangolin), both 32 and 64 bit, is the only operating system officially supported. Support for **Ubuntu 14.04 LTS** is scheduled for release 1.4. If you are familiar with Python code you can already install the OpenQuake Engine on Ubuntu 14.04 using the [following instructions](Installing-the-OpenQuake-Engine-from-source-code-on-14.04.md).
 
**All product and company names are trademarks™ or registered trademarks© of their respective holders. GEM is is not affiliated with and does not endorse any of the products or companies mentioned on this page.**

### Single node configuration

Small to medium hazard calculations and small risk calculations can run on a laptop or an equivalent cloud server: 8GB of RAM and 4 cores with a 250GB of disk space.  Using >= 7.2k RPM disks or solid-state drives (SSD) will improve performance.

More serious calculations would be better handled by a single server with a hardware RAID support: our "hope" server is a Dell® PowerEdge™ R420 with 12 cores (2 x Intel® Xeon™ E5-2430) 64GB of RAM and 4x2TB disks in a RAID 10 configuration and a hardware RAID controller (Dell® PERC H710).  It is used now primarily to host databases but for a little while it was the best machine we had in Pavia and was used to run calculations too.

### Large scale/multi-node configuration

Our cluster master node "wilson" is a Dell® PowerEdge™ R720 with 16 Xeon cores, 128GB of RAM and two RAID arrays, one with faster disks for the OpenQuake engine DB and a larger slower one for more persistent data storage.  This sort of machine would be able to handle some pretty large calculations as a single server but can also be used as the master node if you find you need to add more machines to form a cluster; so this might be a good starting point if it is compatible with your budget.

For our largest calculations on a continental or global scale we use a cluster composed of "wilson" (see above) acting as a "master" and 4 worker nodes (Dell® PowerEdge™ M915 blades) each with 4x 16 cores AMD® Opteron™ and 128GB of RAM.  Worker nodes do not need much disk since the data is stored in the master DB.
