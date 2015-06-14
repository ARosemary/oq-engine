# Copyright (c) 2010-2014, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

"""Functions for getting information about completed jobs and
calculation outputs, as well as exporting outputs from the database to various
file formats."""


import os
import zipfile
from openquake.engine.db import models
from openquake.engine.logs import LOG
from openquake.baselib.general import CallableDict
from openquake.commonlib.export import export as ds_export
from openquake.commonlib.datastore import DataStore

export_output = CallableDict()


class DataStoreExportError(Exception):
    pass


def zipfiles(fnames, archive):
    """
    Build a zip archive from the given file names.

    :param fnames: list of path names
    :param archive: path of the archive
    :returns: the given archive path
    """
    z = zipfile.ZipFile(archive, 'w')
    for f in fnames:
        z.write(f)
    z.close()
    return archive


@export_output.add(('datastore', 'csv'), ('datastore', 'xml'))
def export_from_datastore(output_key, output, target):
    """
    :param output_key: a pair ('datastore', fmt)
    :param output: an Output instance
    :param target: a directory, temporary when called from the engine server
    """
    fmt = output_key[1]
    dstore = DataStore(output.oq_job.id)
    try:
        exported = ds_export((output.ds_key, fmt), dstore)
    except KeyError:
        raise DataStoreExportError(
            'Could not export %s in %s' % (output.ds_key, fmt))
    if not exported:
        raise DataStoreExportError(
            'Nothing to export for %s' % output.ds_key)
    elif len(exported) > 1:
        archname = output.ds_key.lstrip('/') + '-' + fmt + '.zip'
        return zipfiles(exported, os.path.join(target, archname))
    else:  # single file
        return exported[0]


def export(output_id, target, export_type='xml,geojson,csv'):
    """
    Export the given calculation `output_id` from the database to the
    specified `target` directory in the specified `export_type`.
    """
    output = models.Output.objects.get(id=output_id)
    if isinstance(target, basestring):  # create target directory
        makedirs(target)
    for exptype in export_type.split(','):
        key = (output.output_type, exptype)
        if key in export_output:
            return export_output(key, output, target)
    LOG.warn(
        'No "%(fmt)s" exporter is available for "%(output_type)s"'
        ' outputs' % dict(fmt=export_type, output_type=output.output_type))

#: Used to separate node labels in a logic tree path
LT_PATH_JOIN_TOKEN = '_'


def makedirs(path):
    """
    Make all of the directories in the ``path`` using `os.makedirs`.
    """
    if os.path.exists(path):
        if not os.path.isdir(path):
            # If it's not a directory, we can't do anything.
            # This is a problem
            raise RuntimeError('%s already exists and is not a directory.'
                               % path)
    else:
        os.makedirs(path)


def get_outputs(job_id, output_type=None):
    """Get all :class:`openquake.engine.db.models.Output` objects associated
    with the specified job and output_type.

    :param int job_id:
        ID of a :class:`openquake.engine.db.models.OqJob`.
    :param str output_type:
        the output type; if None, return all outputs
    :returns:
        :class:`django.db.models.query.QuerySet` of
        :class:`openquake.engine.db.models.Output` objects.
    """
    queryset = models.Output.objects.filter(oq_job=job_id)
    if output_type:
        return queryset.filter(output_type=output_type)
    return queryset
