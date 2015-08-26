#  -*- coding: utf-8 -*-
#  vim: tabstop=4 shiftwidth=4 softtabstop=4

#  Copyright (c) 2015, GEM Foundation

#  OpenQuake is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

#  OpenQuake is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU Affero General Public License
#  along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

from openquake.baselib.general import CallableDict
from openquake.engine.utils import tasks  # really UGLY hack:
# we need to monkey patch commonlib.parallel *before* importing
# calculators.views; the ugliness will disappear when the engine
# calculator will disappear
from openquake.calculators.views import rst_table
from openquake.engine.db import models

import numpy

view = CallableDict()


@view.add('mean_avg_losses')
def mean_avg_losses(key, job_id):
    outputs = models.Output.objects.filter(
        oq_job=job_id, display_name__contains='Mean Loss Curves'
    ).order_by('display_name') or models.Output.objects.filter(
        oq_job=job_id, display_name__contains='loss curves. type='
    ).order_by('display_name')  # there could be a single realization
    if len(outputs) == 0:
        return 'No %s for calculation %d' % (key, job_id)
    data_by_lt = {}
    for output in outputs:
        lt = output.loss_curve.loss_type
        data = output.loss_curve.losscurvedata_set.all().order_by('asset_ref')
        data_by_lt[lt] = {row.asset_ref: row.average_loss for row in data}
    dt_list = [('asset_ref', '|S20')] + [(str(ltype), numpy.float32)
                                         for ltype in sorted(data_by_lt)]
    avg_loss_dt = numpy.dtype(dt_list)
    losses = numpy.zeros(len(data_by_lt[lt]), avg_loss_dt)
    for lt, loss_by_asset in data_by_lt.items():
        assets = sorted(loss_by_asset)
        losses[lt] = [loss_by_asset[a] for a in assets]
    losses['asset_ref'] = assets
    return rst_table(losses)
