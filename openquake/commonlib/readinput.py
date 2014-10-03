import numpy

from openquake.hazardlib import geo, site
from openquake.nrmllib.node import read_nodes, LiteralNode, context
from openquake.risklib.workflows import Asset

from openquake.commonlib import valid
from openquake.commonlib.oqvalidation import \
    fragility_files, vulnerability_files
from openquake.commonlib.riskmodels import \
    get_fragility_functions, get_imtls_from_vulnerabilities, get_vfs
from openquake.commonlib.converter import Converter
from openquake.commonlib.source import ValidNode, RuptureConverter


def get_mesh(oqparam):
    """
    Extract the mesh of points to compute from the sites,
    the sites_csv, the region or the exposure.

    :param oqparam:
        an :class:`openquake.commonlib.oqvalidation.OqParam` instance
    """
    if getattr(oqparam, 'sites', None):
        lons, lats = zip(*oqparam.sites)
        return geo.Mesh(numpy.array(lons), numpy.array(lats))
    elif 'site' in oqparam.inputs:
        csv_data = open(oqparam.inputs['site'], 'U').read()
        coords = valid.coordinates(
            csv_data.strip().replace(',', ' ').replace('\n', ','))
        lons, lats = zip(*coords)
        return geo.Mesh(numpy.array(lons), numpy.array(lats))
    elif getattr(oqparam, 'region', None):
        # close the linear polygon ring by appending the first
        # point to the end
        firstpoint = geo.Point(*oqparam.region[0])
        points = [geo.Point(*xy) for xy in oqparam.region] + [firstpoint]
        return geo.Polygon(points).discretize(oqparam.region_grid_spacing)
    elif 'exposure' in oqparam.inputs:
        exposure = Converter.from_nrml(oqparam.inputs['exposure'])
        coords = sorted(set((s.lon, s.lat)
                            for s in exposure.tableset.tableLocation))
        lons, lats = zip(*coords)
        return geo.Mesh(numpy.array(lons), numpy.array(lats))


class SiteModelNode(LiteralNode):
    validators = valid.parameters(site=valid.site_param)


def get_site_model(oqparam):
    """
    Convert the NRML file into an iterator over 6-tuple of the form
    (z1pt0, z2pt5, measured, vs30, lon, lat)

    :param oqparam:
        an :class:`openquake.commonlib.oqvalidation.OqParam` instance
    """
    for node in read_nodes(oqparam.inputs['site_model'],
                           lambda el: el.tag.endswith('site'),
                           SiteModelNode):
        yield ~node


def get_site_collection(oqparam, mesh=None, site_ids=None,
                        site_model_params=None):
    """
    Returns a SiteCollection instance by looking at the points and the
    site model defined by the configuration parameters.

    :param oqparam:
        an :class:`openquake.commonlib.oqvalidation.OqParam` instance
    :param mesh:
        a mesh of hazardlib points; if None the mesh is
        determined by invoking get_mesh
    :param site_ids:
        a list of integers to identify the points; if None, a
        range(1, len(points) + 1) is used
    :param site_model_params:
        object with a method ,get_closest returning the closest site
        model parameters
    """
    mesh = mesh or get_mesh(oqparam)
    site_ids = site_ids or range(1, len(mesh) + 1)
    if oqparam.inputs.get('site_model'):
        sitecol = []
        for i, pt in zip(site_ids, mesh):
            param = site_model_params.\
                get_closest(pt.longitude, pt.latitude)
            sitecol.append(
                site.Site(pt, param.vs30, param.vs30_type == 'measured',
                          param.z1pt0, param.z2pt5, i))
        return site.SiteCollection(sitecol)

    # else use the default site params
    return site.SiteCollection.from_points(
        mesh.lons, mesh.lats, site_ids, oqparam)


def get_rupture(oqparam):
    """
    Returns a hazardlib rupture by reading the `rupture_model` file.

    :param oqparam:
        an :class:`openquake.commonlib.oqvalidation.OqParam` instance
    """
    conv = RuptureConverter(oqparam.rupture_mesh_spacing)
    rup_model = oqparam.inputs['rupture_model']
    rup_node, = read_nodes(rup_model, lambda el: 'Rupture' in el.tag,
                           ValidNode)
    return conv.convert_node(rup_node)


def get_source_models(oqparam):
    """
    Read all the source models specified in oqparam.
    Yield pairs (fname, sources).

    :param oqparam:
        an :class:`openquake.commonlib.oqvalidation.OqParam` instance
    """
    for fname in oqparam.inputs['source']:
        srcs = read_nodes(fname, lambda elem: 'Source' in elem.tag, ValidNode)
        yield fname, srcs


def get_imtls(oqparam):
    """
    Return a dictionary {imt_str: intensity_measure_levels}

    :param oqparam:
        an :class:`openquake.commonlib.oqvalidation.OqParam` instance
    """
    if hasattr(oqparam, 'intensity_measure_types'):
        imtls = dict.fromkeys(oqparam.intensity_measure_types)
    elif hasattr(oqparam, 'intensity_measure_types_and_levels'):
        imtls = oqparam.intensity_measure_types_and_levels
    elif vulnerability_files(oqparam.inputs):
        imtls = get_imtls_from_vulnerabilities(oqparam.inputs)
    elif fragility_files(oqparam.inputs):
        fname = oqparam.inputs['fragility']
        _damage_states, ffs = get_fragility_functions(fname)
        imtls = {fset.imt: fset.imls for fset in ffs.values()}
    else:
        raise ValueError('Missing intensity_measure_types_and_levels, '
                         'vulnerability file and fragility file')
    return imtls


def get_vulnerability_functions(oqparam):
    """Return a dict (imt, taxonomy) -> vf"""
    return get_vfs(oqparam.inputs)

############################ exposure #############################


class ExposureNode(LiteralNode):
    validators = valid.parameters(
        occupants=valid.positivefloat,
        value=valid.positivefloat,
        deductible=valid.positivefloat,
        insuranceLimit=valid.positivefloat,
        location=valid.point2d,
    )


def get_exposure(oqparam):
    """
    Read the exposure and yields :class:`openquake.risklib.workflows.Asset`
    instances.
    """
    relevant_cost_types = set(vulnerability_files(oqparam.inputs))
    fname = oqparam.inputs['exposure']
    time_event = getattr(oqparam, 'time_event')
    for asset in read_nodes(fname,
                            lambda node: node.tag.endswith('asset'),
                            ExposureNode):
        values = {}
        deductibles = {}
        insurance_limits = {}
        retrofitting_values = {}

        with context(fname, asset):
            asset_id = asset['id']
            taxonomy = asset['taxonomy']
            number = asset['number']
            location = ~asset.location
        with context(fname, asset.costs):
            for cost in asset.costs:
                cost_type = cost['type']
                if cost_type not in relevant_cost_types:
                    continue
                values[cost_type] = cost['value']
                deductibles[cost_type] = cost.attrib.get('deductible')
                insurance_limits[cost_type] = cost.attrib.get('insuranceLimit')
            # check we are not missing a cost type
            assert set(values) == relevant_cost_types

        if time_event:
            for occupancy in asset.occupancies:
                with context(fname, occupancy):
                    if occupancy['period'] == time_event:
                        values['fatalities'] = occupancy['occupants']
                        break

        yield Asset(asset_id, taxonomy, number, location,
                    values, deductibles, insurance_limits, retrofitting_values)
