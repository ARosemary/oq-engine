from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url

# each url is prefixed with /v1/calc/
urlpatterns = patterns(
    'openquakeserver.engine.views',
    url(r'^hazard$', 'calc_hazard'),
    url(r'^hazard/(\d+)$', 'calc_hazard_info'),
    url(r'^hazard/(\d+)/results$', 'calc_hazard_results'),

    url(r'^risk$', 'calc_risk'),
    url(r'^risk/(\d+)$', 'calc_risk_info'),
    url(r'^risk/(\d+)/results$', 'calc_risk_results'),
)
