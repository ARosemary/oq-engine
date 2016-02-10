# Running the OpenQuake Engine on multiple Ubuntu nodes (cluster configuration)

## Overall architecture
The nodes must all be able to communicate with a single PostresSQL database and a single RabbitMQ server.
One common configuration is to install and deploy the two services on a single "master" node, but other configurations are possible. It is not necessary and not normally recommended to configure PostgreSQL or RabbitMQ on a worker node.

## Initial install
On all nodes,install the python-oq-engine package as described in [OpenQuake Engine installation](Installing-the-OpenQuake-Engine.md) or [OpenQuake Engine Master installation](Installing-the-OpenQuake-Engine-Nightly.md).

## Postgres configuration
The default Postgres configuration does not permit access from other machines: the file `/etc/postgresql/9.3/main/pg_hba.conf` should be modified to allow access to the "openquake2" database from the worker nodes, an example excerpt follows:

<pre>
host   openquake2   oq_admin        192.168.10.0/8 md5
host   openquake2   oq_job_init     192.168.10.0/8 md5
</pre>

The Postgres manual describes a number of runtime configuration parameters that may need to be adjusted depending on your cluster configuration:

### listen_addresses
* See [http://www.postgresql.org/docs/current/static/runtime-config-connection.html#GUC-LISTEN-ADDRESSES](http://www.postgresql.org/docs/current/static/runtime-config-connection.html#GUC-LISTEN-ADDRESSES)

By default Postres, on Ubuntu, allows connections only from localhost. Since celery workers need to push data back to Postgres, it should be exposed to the cluster network:

`/etc/postgresql/9.3/main/postgresql.conf`
<pre>
# This value should be at least the number of worker cores
listen_addresses = '*'
</pre>

### max_connections 
* See [http://www.postgresql.org/docs/current/static/runtime-config-connection.html#GUC-MAX-CONNECTIONS](http://www.postgresql.org/docs/current/static/runtime-config-connection.html#GUC-MAX-CONNECTIONS)

By default Postres allows a maximum of 100 simultaneous connections. By default celery will create a worker process for each available core and the OpenQuake Engine uses two connection per worker, so max_connections should be at least twice number of available worker cores (2 * CPU in the cluster).

Note that changing max_connections may also imply operating-system level changes, please see [http://www.postgresql.org/docs/current/static/kernel-resources.html](http://www.postgresql.org/docs/current/static/kernel-resources.html) for details.

`/etc/postgresql/9.3/main/postgresql.conf`
<pre>
# This value should be at least the number of worker cores
max_connections = 100
</pre>

Note: you have to **restart every celery node** after a PostgreSQL configuration change or a restart.

## OpenQuake Engine 'master' node configuration File

### Enable Celery

In the master node, the following file should be modified to enable the Celery support:

`/etc/openquake/openquake.cfg:`

```
[celery]
# enable celery only if you have a cluster
use_celery = false
```

Please **NOTE**: the /etc/openquake/openquake.cfg file can be overridden by an openquake.cfg file in the current working directory.

## OpenQuake Engine 'worker' node configuration File
On all worker nodes, the following file should be modified to refer to the Postres and Rabbit servers:

```/etc/openquake/openquake.cfg``` (see the ```/etc/openquake/openquake_workers.cfg``` as reference):
```
[amqp]
# Replace localhost with hostname for RabbitMQ
host = localhost
port = 5672

# See the RabbitMQ "Access Control" page for details of the vhost parameter
# http://www.rabbitmq.com/access-control.html
vhost = /

[database]
name = openquake
# replace localhost with the hostname for the Postgres DB
host = localhost
port = 5432
```

## Running calculations

Jobs can be submitted through the master node using the `oq-engine` command line interface.

### Starting Celery

`celeryd` must run all of the worker nodes. It can be started using the following commands

#### Ubuntu 12.04 / Celery 2
<pre>
cd /usr/share/openquake/engine && celeryd --purge &
</pre>

#### Ubuntu 14.04 / Celery 3
<pre>
cd /usr/share/openquake/engine && celery worker --purge -Ofair &
</pre>

but we strongly suggest to use `supervisord` to manage the celery deamons.

```supervisord``` can be installed with
```bash
sudo apt-get install supervisor
```

An example of configuration for the OpenQuake Engine is available in [supervisor.md](supervisord.md).

## Network and security considerations
The worker nodes should be isolated from the external network using either a dedicated internal network or a firewall.
Additionally, access to the RabbitMQ, and PostgreSQL ports should be limited (again by internal LAN or firewall) so that external traffic is excluded.

It is not recommended to run the Celery daemon as root.
If using `supervisord` (or similar) to execute `celeryd` at boot time please ensure that celery is not run as the _root_ user.

## Storage requirements

Storage requirements depend a lot on the type of calculations run. On a worker node you will need just the space for the operating system, the logs and the OpenQuake installation: less than 20GB are usually enough. Workers can be also diskless (using iSCSI or NFS for example).

On the master node you will also need space for:
- the users' **home** directory (usually located under `/home`): it contains the calculations datastore (`hdf5` files located in the `oqdata` folder)
- the PostgreSQL `openquake2` database (on Ubuntu is usually located under `/var/lib/postgres`)
- RabbitMQ mnesia dir (on Ubuntu usually located under `/var/lib/rabbitmq`)

On large installation we strongly suggest to create separate partition for `/home`, `/var`, PostgreSQL (`/var/lib/postgres`) and RabbitMQ (`/var/lib/rabbitmq`).
Those partitions should be stored on fast local disks or on a high performance SAN (i.e. using a FC or a 10Gbps link).

