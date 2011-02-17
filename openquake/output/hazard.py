# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
This module provides classes that serialize hazard-related objects
to NRML format.

* Hazard curves:

For the serialization of hazard curves, it currently takes 
all the lxml object model in memory
due to the fact that curves can be grouped by IDmodel and
IML. Couldn't find a way to do so writing an object at a
time without making a restriction to the order on which
objects are received.

* Hazard maps:

Hazard maps are serialized per object (=Site) as implemented 
in the base class.

* Ground Motion Fields (GMFs):

GMFs are serialized per object (=Site) as implemented in the base class.
"""

from lxml import etree

from openquake import shapes
from openquake import writer

from openquake.xml import NSMAP, NRML, GML, NSMAP_WITH_QUAKEML

NRML_GML_ID = 'n1'
HAZARDRESULT_GML_ID = 'hr1'
GMFS_GML_ID = 'gmfs_1'
GMF_GML_ID = 'gmf_1'
SRS_EPSG_4326 = 'epsg:4326'


class HazardCurveXMLWriter(writer.FileWriter):
    """This class writes an hazard curve into the NRML format."""

    def __init__(self, path):
        super(HazardCurveXMLWriter, self).__init__(path)

        self.nrml_el = None
        self.result_el = None
        self.curves_per_branch_label = {}
        self.hcnode_counter = 0
        self.hcfield_counter = 0

    def close(self):
        """Override the default implementation writing all the
        collected lxml object model to the stream."""

        if self.nrml_el is None:
            error_msg = "You need to add at least a curve to build " \
                        "a valid output!"
            raise RuntimeError(error_msg)

        self.file.write(etree.tostring(self.nrml_el, pretty_print=True,
            xml_declaration=True, encoding="UTF-8"))

        super(HazardCurveXMLWriter, self).close()
            
    def write(self, point, values):
        """Write an hazard curve.
        
        point must be of type shapes.Site
        values is a dictionary that matches the one produced by the
        parser nrml.NrmlFile
        """

        # if we are writing the first hazard curve, create wrapping elements
        if self.nrml_el is None:
            
            # nrml:nrml, needs gml:id
            self.nrml_el = etree.Element("%snrml" % NRML, nsmap=NSMAP)

            _set_gml_id_if_present("nrml_id", values,
                    NRML_GML_ID, self.nrml_el)
            
            # nrml:hazardResult, needs gml:id
            self.result_el = etree.SubElement(self.nrml_el, 
                "%shazardResult" % NRML)

            _set_gml_id_if_present("hazres_id", values,
                    HAZARDRESULT_GML_ID, self.result_el)

            # nrml:config
            config_el = etree.SubElement(self.result_el, "%sconfig" % NRML)
            
            # nrml:hazardProcessing
            hazard_processing_el = etree.SubElement(config_el, 
                "%shazardProcessing" % NRML)
            
            # the following XML attributes are all optional
            _set_optional_attributes(hazard_processing_el, values,
                ('investigationTimeSpan', 'IDmodel', 'saPeriod', 'saDamping'))

        # check if we have hazard curves for an end branch label, or
        # for mean/median/quantile
        if 'endBranchLabel' in values and 'statistics' in values:
            error_msg = "hazardCurveField cannot have both an end branch " \
                        "and a statistics label"
            raise ValueError(error_msg)
        elif 'endBranchLabel' in values:
            curve_label = values['endBranchLabel']
        elif 'statistics' in values:
            curve_label = values['statistics']
        else:
            error_msg = "hazardCurveField has to have either an end branch " \
                        "or a statistics label"
            raise ValueError(error_msg)
        
        try:
            hazard_curve_field_el = self.curves_per_branch_label[curve_label]
        except KeyError:

            # nrml:hazardCurveField, needs gml:id
            hazard_curve_field_el = etree.SubElement(self.result_el, 
                "%shazardCurveField" % NRML)

            _set_gml_id_if_present("hcfield_id", values,
                    "hcf_%s" % self.hcfield_counter, hazard_curve_field_el)

            if "hcfield_id" not in values:
                self.hcfield_counter += 1

            if 'endBranchLabel' in values:
                hazard_curve_field_el.set("endBranchLabel", 
                    str(values["endBranchLabel"]))
            elif 'statistics' in values:
                hazard_curve_field_el.set("statistics", 
                    str(values["statistics"]))
                if 'quantileValue' in values:
                    hazard_curve_field_el.set("quantileValue", 
                        str(values["quantileValue"]))

            # nrml:IML
            iml_el = etree.SubElement(hazard_curve_field_el, "%sIML" % NRML)
            iml_el.text = " ".join([str(x) for x in values["IMLValues"]])
            iml_el.set("IMT", str(values["IMT"]))

            self.curves_per_branch_label[curve_label] = hazard_curve_field_el
        
        # nrml:HCNode, needs gml:id
        hcnode_el = etree.SubElement(hazard_curve_field_el, "%sHCNode" % NRML)

        _set_gml_id_if_present("hcnode_id", values,
                "hcn_%s" % self.hcnode_counter, hcnode_el)

        if "hcnode_id" not in values:
            self.hcnode_counter += 1

        # nrml:site, nrml:Point
        point_el = etree.SubElement(etree.SubElement(
                hcnode_el, "%ssite" % NRML), "%sPoint" % GML)

        point_el.set("srsName", SRS_EPSG_4326)

        pos_el = etree.SubElement(point_el, "%spos" % GML)
        pos_el.text = "%s %s" % (point.longitude, point.latitude)

        # nrml:hazardCurve, nrml:poE
        poe_el = etree.SubElement(etree.SubElement(
                hcnode_el, "%shazardCurve" % NRML), "%spoE" % NRML)

        poe_el.text = " ".join([str(x) for x in values["PoEValues"]])


class HazardMapXMLWriter(writer.FileWriter):
    """This class serializes hazard map information
    to NRML format.
    """

    root_tag = "%snrml" % NRML
    hazard_result_tag = "%shazardResult" % NRML
    config_tag = "%sconfig" % NRML
    hazard_processing_tag = "%shazardProcessing" % NRML
    
    hazard_map_tag = "%shazardMap" % NRML

    node_tag = "%sHMNode" % NRML
    site_tag = "%sHMSite" % NRML
    vs30_tag = "%svs30" % NRML

    point_tag = "%sPoint" % GML
    pos_tag = "%spos" % GML
    iml_tag = "%sIML" % NRML

    PROCESSING_ATTRIBUTES_TO_CHECK = (
        {'name': 'investigationTimeSpan', 'required': False},)

    MAP_ATTRIBUTES_TO_CHECK = (
        {'name': 'poE', 'required': True}, 
        {'name': 'IMT', 'required': True}, 
        {'name': 'endBranchLabel', 'required': False}, 
        {'name': 'statistics', 'required': False}, 
        {'name': 'quantileValue', 'required': False})

    NRML_DEFAULT_ID = 'nrml'
    HAZARD_RESULT_DEFAULT_ID = 'hr'
    HAZARD_MAP_DEFAULT_ID = 'hm'
    HAZARD_MAP_NODE_ID_PREFIX = 'n_'

    def __init__(self, path):
        super(HazardMapXMLWriter, self).__init__(path)
        self.hmnode_counter = 0
        self.parent_node = None
        self.hazard_processing_node = None

    def write(self, point, val):
        """Writes hazard map for one site.

        point must be of type shapes.Site
        val is a dictionary like this:

        {'IML': 0.8,
         'IMT': 'PGA',
         'poE': 0.1,
         'endBranchLabel': '1',
         'vs30': 760.0,
         'investigationTimeSpan': 50.0
        }
        """

        if isinstance(point, shapes.GridPoint):
            point = point.site.point
        if isinstance(point, shapes.Site):
            point = point.point
        self._append_node(point, val, self.parent_node)

    def write_header(self):
        """Header (i.e., common) information for all nodes."""

        self.root_node = etree.Element(self.root_tag, nsmap=NSMAP)
        self.root_node.attrib['%sid' % GML] = self.NRML_DEFAULT_ID

        hazard_result_node = etree.SubElement(self.root_node, 
            self.hazard_result_tag, nsmap=NSMAP)
        hazard_result_node.attrib['%sid' % GML] = self.HAZARD_RESULT_DEFAULT_ID

        config_node = etree.SubElement(hazard_result_node, 
            self.config_tag, nsmap=NSMAP)

        self.hazard_processing_node = etree.SubElement(config_node, 
            self.hazard_processing_tag, nsmap=NSMAP)

        # parent node for hazard map nodes: hazardMap
        self.parent_node = etree.SubElement(hazard_result_node, 
            self.hazard_map_tag, nsmap=NSMAP)
        self.parent_node.attrib['%sid' % GML] = self.HAZARD_MAP_DEFAULT_ID

    def write_footer(self):
        """Serialize tree to file."""

        if self._ensure_all_attributes_set():
            et = etree.ElementTree(self.root_node)
            et.write(self.file, pretty_print=True, xml_declaration=True,
                    encoding="UTF-8")
        else:
            error_msg = "not all required attributes set in hazard curve " \
                        "dataset"
            raise ValueError(error_msg)
    
    def _append_node(self, point, val, parent_node):
        """Write HMNode element."""
        
        self.hmnode_counter += 1
        node_node = etree.SubElement(parent_node, self.node_tag, nsmap=NSMAP)
        node_node.attrib["%sid" % GML] = "%s%s" % (
            self.HAZARD_MAP_NODE_ID_PREFIX, self.hmnode_counter)

        site_node = etree.SubElement(node_node, self.site_tag, nsmap=NSMAP)
        point_node = etree.SubElement(site_node, self.point_tag, nsmap=NSMAP)
        point_node.attrib['srsName'] = 'epsg:4326'

        pos_node = etree.SubElement(point_node, self.pos_tag, nsmap=NSMAP)
        pos_node.text = "%s %s" % (str(point.x), str(point.y))

        if 'vs30' in val:
            vs30_node = etree.SubElement(site_node, self.vs30_tag, 
                nsmap=NSMAP)
            vs30_node.text = str(val['vs30'])

        iml_node = etree.SubElement(node_node, self.iml_tag, nsmap=NSMAP)
        iml_node.text = str(val['IML'])

        # check/set common attributes
        # TODO(fab): this could be moved to common base class 
        # of all serializers
        self._set_common_attributes(self.PROCESSING_ATTRIBUTES_TO_CHECK, 
            self.hazard_processing_node, val)
        self._set_common_attributes(self.MAP_ATTRIBUTES_TO_CHECK, 
            parent_node, val)

    def _set_common_attributes(self, attr_list, node, val):
        """Set common XML attributes, if necessary. Check if consistent
        values are given for all hazard map nodes. If hazard map node
        attributes dictionary does not have the item set, do nothing.
        """
        for attr in attr_list:
            if attr['name'] in val:
                if attr['name'] not in node.attrib:
                    node.attrib[attr['name']] = str(val[attr['name']])
                elif node.attrib[attr['name']] != str(val[attr['name']]):
                    error_msg = "not all nodes of the hazard map have the " \
                        "same value for common attribute %s" % attr['name'] 
                    raise ValueError(error_msg)

    def _ensure_all_attributes_set(self):
        if (self._ensure_attributes_set(self.PROCESSING_ATTRIBUTES_TO_CHECK, 
                                        self.hazard_processing_node) and 
             self._ensure_attributes_set(self.MAP_ATTRIBUTES_TO_CHECK, 
                                         self.parent_node) and
             self._ensure_attribute_rules()):
            return True
        else:
            return False

    def _ensure_attribute_rules(self):
        
        # special checks: end branch label and statistics
        if 'endBranchLabel' in self.parent_node.attrib:

            # ensure that neither statistics nor quantileValue is set
            # together with endBranchLabel
            if ('statistics' in self.parent_node.attrib or
                'quantileValue' in self.parent_node.attrib):

                error_msg = "attribute endBranchLabel cannot be used " \
                            "together with statistics/quantileValue"
                raise ValueError(error_msg)

        elif 'statistics' not in self.parent_node.attrib:

            error_msg = "either attribute endBranchLabel or attribute " \
                        "statistics has to be set"
            raise ValueError(error_msg)

        return True


    def _ensure_attributes_set(self, attr_list, node):
        for attr in attr_list:
            if attr['name'] not in node.attrib and attr['required'] is True:
                return False
        return True


class GMFXMLWriter(writer.FileWriter):
    """This class serializes ground motion field (GMF) informatiuon
    to NRML format.

    As of now, only the GMFNode information is supported. GMPEParameters is
    serialized as a stub with the only attribute that is formally required
    (but doesn't have a useful definition in the schema).
    Rupture information and full GMPEParameters are currently 
    not supported."""

    root_tag = NRML + "nrml"
    hazard_result_tag = NRML + "hazardResult"
    config_tag = NRML + "config"
    hazard_processing_tag = NRML + "hazardProcessing"
    gmpe_params_tag = NRML + "GMPEParameters"
    groun_motion_field_set_tag = NRML + "groundMotionFieldSet"
    field_tag = NRML + "GMF"
    node_tag = NRML + "GMFNode"
    site_tag = NRML + "site"
    point_tag = GML + "Point"
    pos_tag = GML + "pos"
    ground_motion_attr = "groundMotion"

    def __init__(self, path):
        super(GMFXMLWriter, self).__init__(path)
        self.node_counter = 0
        
        # <GMF/> where all the fields are appended
        self.parent_node = None

        # <nrml/> the root of the document
        self.root_node = None

    def write(self, point, val):
        """Writes GMF for one site.

        point must be of type shapes.Site or shapes.GridPoint
        val is a dictionary:

        {'groundMotion': 0.8}
        """
        if isinstance(point, shapes.GridPoint):
            point = point.site.point
        if isinstance(point, shapes.Site):
            point = point.point
        self._append_site_node(point, val, self.parent_node)

    def write_header(self):
        """Write out the file header."""

        # TODO(fab): support rupture element (not implemented so far)
        # TODO(fab): support full GMPEParameters (not implemented so far)

        self.root_node = etree.Element(
                GMFXMLWriter.root_tag, nsmap=NSMAP_WITH_QUAKEML)

        _set_gml_id(self.root_node, NRML_GML_ID)
        
        hazard_result_node = etree.SubElement(self.root_node,
                GMFXMLWriter.hazard_result_tag, nsmap=NSMAP)

        _set_gml_id(hazard_result_node, HAZARDRESULT_GML_ID)
        
        config_node = etree.SubElement(hazard_result_node,
                GMFXMLWriter.config_tag, nsmap=NSMAP)

        hazard_processing_node = etree.SubElement(config_node,
                GMFXMLWriter.hazard_processing_tag, nsmap=NSMAP)

        # stubbed value, not yet implemented...
        hazard_processing_node.set(
                "%sinvestigationTimeSpan" % NRML, str(50.0))

        ground_motion_field_set_node = etree.SubElement(
                hazard_result_node,
                GMFXMLWriter.groun_motion_field_set_tag, nsmap=NSMAP)

        _set_gml_id(ground_motion_field_set_node, GMFS_GML_ID)


        gmpe_params_node = etree.SubElement(
                ground_motion_field_set_node,
                GMFXMLWriter.gmpe_params_tag, nsmap=NSMAP)

        # stubbed value, not yet implemented...
        gmpe_params_node.set("%sIMT" % NRML, "PGA")

        # right now, all the sites are appended to one GMF
        self.parent_node = etree.SubElement(
                ground_motion_field_set_node,
                GMFXMLWriter.field_tag, nsmap=NSMAP)

        _set_gml_id(self.parent_node, GMF_GML_ID)

    def write_footer(self):
        """Write out the file footer."""
        et = etree.ElementTree(self.root_node)
        et.write(self.file, pretty_print=True, xml_declaration=True,
                 encoding="UTF-8")

    def _append_site_node(self, point, val, parent_node):
        """Write a single GMFNode element."""

        gmf_node = etree.SubElement(
                parent_node, GMFXMLWriter.node_tag, nsmap=NSMAP)
        
        _set_gml_id(gmf_node, "node%s" % self.node_counter)
        
        site_node = etree.SubElement(
                gmf_node, GMFXMLWriter.site_tag, nsmap=NSMAP)

        point_node = etree.SubElement(site_node,
                GMFXMLWriter.point_tag, nsmap=NSMAP)

        pos_node = etree.SubElement(
                point_node, GMFXMLWriter.pos_tag, nsmap=NSMAP)

        pos_node.text = "%s %s" % (str(point.x), str(point.y))

        ground_motion_node = etree.SubElement(
                gmf_node, GMFXMLWriter.ground_motion_attr, nsmap=NSMAP)

        ground_motion_node.text = str(val[self.ground_motion_attr])

        self.node_counter += 1


def _set_optional_attributes(element, value_dict, attr_keys):
    """Set the attributes for the given element specified
    in attr_keys if they are present in the value_dict dictionary."""

    for curr_key in attr_keys:
        if curr_key in value_dict:
            element.set(curr_key, str(value_dict[curr_key]))


def _set_gml_id(element, gml_id):
    """Set the attribute gml:id for the given element."""
    element.set("%sid" % GML, str(gml_id))


def _set_gml_id_if_present(id_key, values, default_id, element):
    """Set the attribute gml:id using the input dictionary if present,
    use a default one otherwise."""

    if id_key in values:
        _set_gml_id(element, str(values[id_key]))
    else:
        _set_gml_id(element, default_id)
