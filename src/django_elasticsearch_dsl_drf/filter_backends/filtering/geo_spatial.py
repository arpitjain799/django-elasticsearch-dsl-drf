"""
Geo spatial filtering backend.
"""

from elasticsearch_dsl.query import Q
from rest_framework.filters import BaseFilterBackend

from six import string_types

from ...constants import (
    ALL_GEO_SPATIAL_LOOKUP_FILTERS_AND_QUERIES,
    LOOKUP_FILTER_GEO_DISTANCE,
)
from ..mixins import FilterBackendMixin

__title__ = 'django_elasticsearch_dsl_drf.filter_backends.filtering.common'
__author__ = 'Artur Barseghyan <artur.barseghyan@gmail.com>'
__copyright__ = '2017 Artur Barseghyan'
__license__ = 'GPL 2.0/LGPL 2.1'
__all__ = ('GeoSpatialFilteringFilterBackend',)


class GeoSpatialFilteringFilterBackend(BaseFilterBackend, FilterBackendMixin):
    """Geo-spatial filtering filter backend for Elasticsearch.

    Example:

        >>> from django_elasticsearch_dsl_drf.constants import (
        >>>     LOOKUP_FILTER_GEO_DISTANCE,
        >>> )
        >>> from django_elasticsearch_dsl_drf.filter_backends import (
        >>>     GeoSpatialFilteringFilterBackend
        >>> )
        >>> from django_elasticsearch_dsl_drf.views import BaseDocumentViewSet
        >>>
        >>> # Local article document definition
        >>> from .documents import ArticleDocument
        >>>
        >>> # Local article document serializer
        >>> from .serializers import ArticleDocumentSerializer
        >>>
        >>> class ArticleDocumentView(BaseDocumentViewSet):
        >>>
        >>>     document = ArticleDocument
        >>>     serializer_class = ArticleDocumentSerializer
        >>>     filter_backends = [GeoSpatialFilteringFilterBackend,]
        >>>     geo_spatial_filter_fields = {
        >>>         'loc': 'location',
        >>>         'location': {
        >>>             'field': 'location',
        >>>             'lookups': [
        >>>                 LOOKUP_FILTER_GEO_DISTANCE,
        >>>             ],
        >>>         }
        >>> }
    """

    @classmethod
    def prepare_filter_fields(cls, view):
        """Prepare filter fields.

        :param view:
        :type view: rest_framework.viewsets.ReadOnlyModelViewSet
        :return: Filtering options.
        :rtype: dict
        """
        filter_fields = view.geo_spatial_filter_fields

        for field, options in filter_fields.items():
            if options is None or isinstance(options, string_types):
                filter_fields[field] = {
                    'field': options or field
                }
            elif 'field' not in filter_fields[field]:
                filter_fields[field]['field'] = field

            if 'lookups' not in filter_fields[field]:
                filter_fields[field]['lookups'] = tuple(
                    ALL_GEO_SPATIAL_LOOKUP_FILTERS_AND_QUERIES
                )

        return filter_fields

    @classmethod
    def get_geo_distance_params(cls, value, field):
        """Get params for `geo_distance` query

        :param value:
        :type value: str
        :return: Params to be used in `geo_distance` query.
        :rtype: dict
        """
        __values = cls.split_lookup_value(value, maxsplit=3)
        __len_values = len(__values)

        if __len_values < 3:
            return {}

        params = {
            'distance': __values[0],
            field: {
                'lat': __values[1],
                'lon': __values[2],
            }
        }

        if __len_values == 4:
            params['distance_type'] = __values[3]
        else:
            params['distance_type'] = 'sloppy_arc'

        return params

    @classmethod
    def apply_query_geo_distance(cls, queryset, options, value):
        """Apply `wildcard` filter.

        :param queryset: Original queryset.
        :param options: Filter options.
        :param value: value to filter on.
        :type queryset: elasticsearch_dsl.search.Search
        :type options: dict
        :type value: str
        :return: Modified queryset.
        :rtype: elasticsearch_dsl.search.Search
        """
        return queryset.query(
            Q(
                'geo_distance',
                **cls.get_geo_distance_params(value, options['field'])
            )
        )

    def get_filter_query_params(self, request, view):
        """Get query params to be filtered on.

        :param request: Django REST framework request.
        :param view: View.
        :type request: rest_framework.request.Request
        :type view: rest_framework.viewsets.ReadOnlyModelViewSet
        :return: Request query params to filter on.
        :rtype: dict
        """
        query_params = request.query_params.copy()

        filter_query_params = {}
        filter_fields = self.prepare_filter_fields(view)
        for query_param in query_params:
            query_param_list = self.split_lookup_filter(
                query_param,
                maxsplit=1
            )
            field_name = query_param_list[0]

            if field_name in filter_fields:
                lookup_param = None
                if len(query_param_list) > 1:
                    lookup_param = query_param_list[1]

                valid_lookups = filter_fields[field_name]['lookups']

                if lookup_param is None or lookup_param in valid_lookups:
                    values = [
                        __value.strip()
                        for __value
                        in query_params.getlist(query_param)
                        if __value.strip() != ''
                    ]

                    if values:
                        filter_query_params[query_param] = {
                            'lookup': lookup_param,
                            'values': values,
                            'field': filter_fields[field_name].get(
                                'field',
                                field_name
                            ),
                            'type': view.mapping
                        }
        return filter_query_params

    def filter_queryset(self, request, queryset, view):
        """Filter the queryset.

        :param request: Django REST framework request.
        :param queryset: Base queryset.
        :param view: View.
        :type request: rest_framework.request.Request
        :type queryset: elasticsearch_dsl.search.Search
        :type view: rest_framework.viewsets.ReadOnlyModelViewSet
        :return: Updated queryset.
        :rtype: elasticsearch_dsl.search.Search
        """
        filter_query_params = self.get_filter_query_params(request, view)
        for options in filter_query_params.values():

            # For all other cases, when we don't have multiple values,
            # we follow the normal flow.
            for value in options['values']:
                # `geo_distance` filter lookup
                if options['lookup'] == LOOKUP_FILTER_GEO_DISTANCE:
                    queryset = self.apply_query_geo_distance(queryset,
                                                             options,
                                                             value)

                # # `geo_distance` filter lookup
                # else:
                #     queryset = self.apply_query_geo_distance(queryset,
                #                                              options,
                #                                              value)
        return queryset