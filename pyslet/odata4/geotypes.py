#! /usr/bin/env python

import collections

from ..py2 import (
    force_text,
    to_text,
    UnicodeMixin,
    )


class GeoItem(object):

    """Abstract mixin class used to identify Geo items

    Geo items are any class that can be added to a
    :class:`GeoCollection` covering points, line strings, polygons,
    multi-points, multi-line strings, multi-polygons and geo collections
    themselves."""

    pass


class Point(GeoItem, UnicodeMixin,
            collections.namedtuple('Point', ['x', 'y'])):

    """Represents a Point type in OData.

    This is a Python namedtuple, almost straight out of the Python docs
    which defines a 2D point that has named fields x and y (in that
    order). The interpretation of x and y will depend on the coordinate
    reference system.  The same type used for both Geography and
    Geometry types.  The values of x and y are always floats, they are
    converted if necessary."""

    __slots__ = ()

    def __new__(cls, x, y):
        # check that x and y are valid
        self = super(Point, cls).__new__(cls, float(x), float(y))
        return self

    @staticmethod
    def from_arg(arg):
        """Returns a point instance

        If arg is already a Point then it is returned, otherwise it is
        iterated to obtain two values to create a new Point instance."""
        if isinstance(arg, Point):
            return arg
        else:
            try:
                x, y = arg
                return Point(x, y)
            except (TypeError, ValueError):
                "Point requires exactly two values"
                raise

    def __unicode__(self):
        return force_text("%.16g %.16g" % self)

    def to_literal(self):
        return force_text("Point(%.16g %.16g)" % self)


class PointLiteral(
        UnicodeMixin,
        collections.namedtuple('PointLiteral', ['srid', 'point'])):

    """Represents a Point literal in OData

    This is a Python namedtuple consisting of an integer 'srid' followed
    by a 'point' of type :class:`Point`."""

    __slots__ = ()

    def __new__(cls, srid, point):
        # check that args are valid
        if not isinstance(point, Point):
            raise TypeError("Expected Point")
        srid = int(srid)
        if srid < 0:
            raise ValueError("SRID must be non-negative")
        self = super(PointLiteral, cls).__new__(cls, srid, point)
        return self

    def __unicode__(self):
        return force_text("SRID=%i;Point(%s)" % self)


class LineString(GeoItem, UnicodeMixin, tuple):

    """Represents a LineString in OData

    A sub-class of tuple containing 2 or more :class:`Point`
    instances."""

    __slots__ = ()

    def __new__(cls, points):
        points = [Point.from_arg(p) for p in points]
        if len(points) < 2:
            raise ValueError("LineString requires at least 2 points")
        self = super(LineString, cls).__new__(cls, points)
        return self

    def __unicode__(self):
        return force_text("(%s)" % ",".join(to_text(p) for p in self))

    def to_literal(self):
        return force_text("LineString%s" % to_text(self))


class LineStringLiteral(
        UnicodeMixin,
        collections.namedtuple('LineStringLiteral', ['srid', 'line_string'])):

    """Represents a LineString literal in OData.

    This is a Python namedtuple consisting of an integer 'srid' followed
    by a 'line_string', an instance of :class:`LineString`"""

    __slots__ = ()

    def __new__(cls, srid, line_string):
        # check that args are valid
        if not isinstance(line_string, LineString):
            line_string = LineString(line_string)
        srid = int(srid)
        if srid < 0:
            raise ValueError("SRID must be non-negative")
        self = super(LineStringLiteral, cls).__new__(
            cls, srid, line_string)
        return self

    def __unicode__(self):
        return force_text("SRID=%i;LineString%s" % self)


class Ring(UnicodeMixin, tuple):

    """Represents a Ring in OData

    A sub-class of tuple containing :class:`Point` instances with the
    constraint that the last and first points in a ring are always the
    same.  As per the ABNF, we allow the degnerate case of a ring
    consisting of a single point."""

    __slots__ = ()

    def __new__(cls, points):
        points = [Point.from_arg(p) for p in points]
        if len(points) < 1:
            raise ValueError("Ring requires at least 1 points")
        elif len(points) > 1 and points[0] != points[-1]:
            raise ValueError("First and last points in ring must match")
        self = super(Ring, cls).__new__(cls, points)
        return self

    @staticmethod
    def from_arg(arg):
        """Returns a Ring instance

        If arg is already a Ring then it is returned, otherwise it is
        used to construct a Ring instance."""
        if isinstance(arg, Ring):
            return arg
        else:
            return Ring(arg)

    def __unicode__(self):
        return force_text("(%s)" % ",".join(to_text(p) for p in self))


class Polygon(GeoItem, UnicodeMixin, tuple):

    """Represents a Polygon in OData

    A sub-class of tuple containing :class:`Ring` instances."""

    __slots__ = ()

    def __new__(cls, rings):
        rings = [Ring.from_arg(r) for r in rings]
        if len(rings) < 1:
            raise ValueError("Polygon requires at 1 ring")
        self = super(Polygon, cls).__new__(cls, rings)
        return self

    @staticmethod
    def from_arg(arg):
        """Returns a Polygon instance

        If arg is already a Polygon instance then it is returned,
        otherwise it is used to construct a Polygon instance."""
        if isinstance(arg, Polygon):
            return arg
        else:
            return Polygon(arg)

    def __unicode__(self):
        return force_text("(%s)" % ",".join(to_text(r) for r in self))

    def to_literal(self):
        return force_text("Polygon%s" % to_text(self))


class PolygonLiteral(
        UnicodeMixin,
        collections.namedtuple('PolygonLiteral', ['srid', 'polygon'])):
    """Represents a Polygon literal in OData.

    This is a Python namedtuple consisting of an integer 'srid' followed
    'polygon', an instance of :class:`Polygon`."""

    __slots__ = ()

    def __new__(cls, srid, polygon):
        # check that args are valid
        if not isinstance(polygon, Polygon):
            polygon = Polygon.from_arg(polygon)
        srid = int(srid)
        if srid < 0:
            raise ValueError("SRID must be non-negative")
        self = super(PolygonLiteral, cls).__new__(cls, srid, polygon)
        return self

    def __unicode__(self):
        return force_text("SRID=%i;Polygon%s" % self)


class MultiPoint(GeoItem, UnicodeMixin, tuple):

    """Represents a MultiPoint in OData

    A sub-class of tuple containing 0 or more :class:`Point`
    instances."""

    __slots__ = ()

    def __new__(cls, points):
        points = [Point.from_arg(p) for p in points]
        self = super(MultiPoint, cls).__new__(cls, points)
        return self

    def __unicode__(self):
        return force_text(",".join("(%s)" % to_text(p) for p in self))

    def to_literal(self):
        return force_text("MultiPoint(%s)" % to_text(self))


class MultiPointLiteral(
        UnicodeMixin,
        collections.namedtuple('MultiPointLiteral', ['srid', 'multipoint'])):

    """Represents a MultiPoint literal in OData.

    This is a Python namedtuple consisting of an integer 'srid' followed
    by 'multipoint', an instance of :class:`MultiPoint`"""

    __slots__ = ()

    def __new__(cls, srid, multipoint):
        # check that args are valid
        if not isinstance(multipoint, MultiPoint):
            multipoint = MultiPoint(multipoint)
        srid = int(srid)
        if srid < 0:
            raise ValueError("SRID must be non-negative")
        self = super(MultiPointLiteral, cls).__new__(
            cls, srid, multipoint)
        return self

    def __unicode__(self):
        return force_text("SRID=%i;MultiPoint(%s)" % self)


class MultiLineString(GeoItem, UnicodeMixin, tuple):

    """Represents a MultiLineString in OData

    A sub-class of tuple containing 0 or more :class:`LineString`
    instances."""

    __slots__ = ()

    def __new__(cls, line_strings):
        line_strings = [l if isinstance(l, LineString) else LineString(l)
                        for l in line_strings]
        self = super(MultiLineString, cls).__new__(cls, line_strings)
        return self

    def __unicode__(self):
        return force_text(",".join(to_text(l) for l in self))

    def to_literal(self):
        return force_text("MultiLineString(%s)" % to_text(self))


class MultiLineStringLiteral(
        UnicodeMixin,
        collections.namedtuple('MultiLineStringLiteral',
                               ['srid', 'multi_line_string'])):

    """Represents a MultiLineString literal in OData.

    This is a Python namedtuple consisting of an integer 'srid' followed
    by 'multi_line_string', an instance of :class:`MultiLineString`"""

    __slots__ = ()

    def __new__(cls, srid, multi_line_string):
        # check that args are valid
        if not isinstance(multi_line_string, MultiLineString):
            multi_line_string = MultiLineString(multi_line_string)
        srid = int(srid)
        if srid < 0:
            raise ValueError("SRID must be non-negative")
        self = super(MultiLineStringLiteral, cls).__new__(
            cls, srid, multi_line_string)
        return self

    def __unicode__(self):
        return force_text("SRID=%i;MultiLineString(%s)" % self)


class MultiPolygon(GeoItem, UnicodeMixin, tuple):

    """Represents a MultiPolygon in OData

    A sub-class of tuple containing 0 or more :class:`Polygon`
    instances."""

    __slots__ = ()

    def __new__(cls, polygons):
        polygons = [p if isinstance(p, Polygon) else Polygon(p)
                    for p in polygons]
        self = super(MultiPolygon, cls).__new__(cls, polygons)
        return self

    def __unicode__(self):
        return force_text(",".join(to_text(p) for p in self))

    def to_literal(self):
        return force_text("MultiPolygon(%s)" % to_text(self))


class MultiPolygonLiteral(
        UnicodeMixin,
        collections.namedtuple('MultiPolygonLiteral',
                               ['srid', 'multi_polygon'])):

    """Represents a MultiPolygon literal in OData.

    This is a Python namedtuple consisting of an integer 'srid' followed
    by 'multi_polygon', an instance of :class:`MultiPolygon`"""

    __slots__ = ()

    def __new__(cls, srid, multi_polygon):
        # check that args are valid
        if not isinstance(multi_polygon, MultiPolygon):
            multi_polygon = MultiPolygon(multi_polygon)
        srid = int(srid)
        if srid < 0:
            raise ValueError("SRID must be non-negative")
        self = super(MultiPolygonLiteral, cls).__new__(
            cls, srid, multi_polygon)
        return self

    def __unicode__(self):
        return force_text("SRID=%i;MultiPolygon(%s)" % self)


class GeoCollection(GeoItem, UnicodeMixin, tuple):

    """Represents a GeoCollection in OData

    A sub-class of tuple containing 0 or more of the basic Geo classes
    :class:`Point`, :class:`LineString`, :class:`Polygon`,
    :class:`MultiPoint`, class:`MultiLineString`, :class:`MultiPolygon`
    and :class:`GeoCollection` itself. (GeoCollection objects can be
    defined recursively)

    .. note::   Although a GeoCollection has 'Collection' in its name it
                behaves like a single 'atomic' value in OData, just like
                the other primitive types such as Int32, String, etc."""

    __slots__ = ()

    def __new__(cls, items):
        for i in items:
            if not isinstance(i, GeoItem):
                raise ValueError("Bad item in GeoCollection: %s" % repr(i))
        self = super(GeoCollection, cls).__new__(cls, items)
        return self

    def to_literal(self):
        return to_text(self)

    def __unicode__(self):
        return force_text(
            "Collection(%s)" % (",".join(i.to_literal() for i in self)))


class GeoCollectionLiteral(
        UnicodeMixin,
        collections.namedtuple('GeoCollection', ['srid', 'items'])):

    """Represents a Geo Collection literal in OData.

    This is a Python namedtuple consisting of an integer 'srid' followed
    by 'items', an instance of :class:`GeoCollection`."""

    __slots__ = ()

    def __new__(cls, srid, items):
        # check that args are valid
        if not isinstance(items, GeoCollection):
            items = GeoCollection(items)
        srid = int(srid)
        if srid < 0:
            raise ValueError("SRID must be non-negative")
        self = super(GeoCollectionLiteral, cls).__new__(
            cls, srid, items)
        return self

    def __unicode__(self):
        return force_text("SRID=%i;%s" % self)
