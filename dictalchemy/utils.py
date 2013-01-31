# vim: set fileencoding=utf-8 :
from __future__ import absolute_import, division

from sqlalchemy.orm import RelationshipProperty, ColumnProperty,\
        SynonymProperty
from sqlalchemy.orm.collections import InstrumentedList

from dictalchemy import constants


def get_relation_keys(model):
    """Get relation keys for a model

    :returns: List of RelationProperties
    """
    return [k.key for k in model.__mapper__.iterate_properties if
            isinstance(k, RelationshipProperty)]


def get_column_keys(model):
    """Get column keys for a model

    :returns: List of column keys
    """
    return [k.key for k in model.__mapper__.iterate_properties if
            isinstance(k, ColumnProperty)]


def get_synonym_keys(model):
    """Get synonym keys for a model

    :returns: List of keys for synonyms
    """
    return [k.key for k in model.__mapper__.iterate_properties if
            isinstance(k, SynonymProperty)]


def get_primary_key_properties(model):
    """Get the column properties that affects a primary key

    :returns: Set of column keys
    """
    # Find primary keys
    primary_keys = set()
    for k in model.__mapper__.iterate_properties:
        if hasattr(k, 'columns'):
            for c in k.columns:
                if c.primary_key:
                    primary_keys.add(k.key)
    return primary_keys


def asdict(model, exclude=None, exclude_underscore=None, exclude_pk=None,
        follow=None, include=None):
    """Get a dict from a model

    This method can also be set on a class directly.

    :param follow: List or dict of relationships that should be followed. \
            If the parameter is a dict the value should be a dict of \
            keyword arguments.
    :param exclude: List of properties that should be excluded, will be \
            merged with model.dictalchemy_exclude.
    :param exclude_pk: If True any column that refers to the primary key will \
            be excluded.
    :param exclude_underscore: Overides model.exclude_underscore if set
    :param include: List of properties that should be included. Use this to \
            allow python properties to be called. This list will be merged \
            with model.dictalchemy_asdict_include.

    :raises: :class:`ValueError` if follow contains a non-existent relationship

    :returns: dict

    """

    if follow == None:
        follow = []
    try:
        follow = dict(follow)
    except ValueError:
        follow = dict.fromkeys(list(follow), {})

    exclude = exclude or []
    exclude += getattr(model, 'dictalchemy_exclude',
            constants.default_exclude) or []
    if exclude_underscore is None:
        exclude_underscore = getattr(model, 'dictalchemy_exclude_underscore',
                constants.default_exclude_underscore)
    if exclude_underscore:
        # Exclude all properties starting with underscore
        exclude += [k.key for k in model.__mapper__.iterate_properties\
                if k.key[0] == '_']
    if exclude_pk is True:
        exclude += get_primary_key_properties(model)

    include = (include or []) + (getattr(model,
        'dictalchemy_asdict_include', None) or [])

    columns = get_column_keys(model)
    synonyms = get_synonym_keys(model)
    relations = get_relation_keys(model)

    data = dict([(k, getattr(model, k)) for k in columns + synonyms + include\
            if k not in exclude])

    for (k, args) in follow.iteritems():
        if k not in relations:
            raise ValueError(\
                    "Key '%r' in parameter 'follow' is not a relations" %\
                    k)
        rel = getattr(model, k)
        if hasattr(rel, 'asdict'):
            data.update({k: rel.asdict(**args)})
        elif isinstance(rel, InstrumentedList):
            children = []
            for child in rel:
                if hasattr(child, 'asdict'):
                    children.append(child.asdict(**args))
                else:
                    children.append(dict(child))
            data.update({k: children})

    return data


def fromdict(model, data, exclude=None, exclude_underscore=None,
        allow_pk=None, follow=None, include=None):
    """Update a model from a dict

    This method updates the following properties on a model:

    * Simple columns
    * Synonyms
    * Simple 1-m relationships

    :param data: dict of data
    :param exclude: list of properties that should be excluded
    :param exclude_underscore: If True underscore properties will be excluded,\
            if set to None model.dictalchemy_exclude_underscore will be used.
    :param allow_pk: If True any column that refers to the primary key will \
            be excluded. Defaults model.dictalchemy_fromdict_allow_pk or \
            dictable.constants.fromdict_allow_pk
    :param follow: Dict of relations that should be followed, the key is the \
            arguments passed to the relation. Relations only works on simple \
            relations, not on lists.
    :param include: list of properties that should be included.

    :raises: :class:`Exception` If a primary key is in data and \
            allow_pk is False

    :returns nothing:

    """

    if follow == None:
        follow = []
    try:
        follow = dict(follow)
    except ValueError:
        follow = dict.fromkeys(list(follow), {})

    exclude = exclude or []
    exclude += getattr(model, 'dictalchemy_exclude',
            constants.default_exclude) or []
    if exclude_underscore is None:
        exclude_underscore = getattr(model, 'dictalchemy_exclude_underscore',
                constants.default_exclude_underscore)

    if exclude_underscore:
        # Exclude all properties starting with underscore
        exclude += [k.key for k in model.__mapper__.iterate_properties\
                if k.key[0] == '_']

    if allow_pk is None:
        allow_pk = getattr(model, 'dictalchemy_fromdict_allow_pk',
                constants.default_fromdict_allow_pk)

    include = (include or []) + (getattr(model,
        'dictalchemy_fromdict_include', None) or [])

    columns = get_column_keys(model)
    synonyms = get_synonym_keys(model)
    relations = get_relation_keys(model)
    primary_keys = get_primary_key_properties(model)

    # Update simple data
    for k, v in data.iteritems():
        if not allow_pk and k in primary_keys:
            raise Exception("Primary key(%r) cannot be updated by fromdict."
                    "Set 'dictalchemy_fromdict_allow_pk' to True in your Model"
                    " or pass 'allow_pk=True'." % k)
        if k in columns + synonyms + include:
            setattr(model, k, v)

    # Update simple relations
    for (k, args) in follow.iteritems():
        if k not in data:
            continue
        if k not in relations:
            raise ValueError(\
                    "Key '%r' in parameter 'follow' is not a relations" %\
                    k)
        rel = getattr(model, k)
        if hasattr(rel, 'asdict'):
            rel.fromdict(data[k], **args)


def iter(model):
    """iter method for models"""
    for i in model.asdict().iteritems():
        yield i


def make_class_dictable(cls, exclude=constants.default_exclude,
        exclude_underscore=constants.default_exclude_underscore,
        fromdict_allow_pk=constants.default_fromdict_allow_pk,
        asdict_include=None, fromdict_include=None):
    """Make a class dictable

    Useful for when the Base class is already defined, for example when using
    Flask-SQLAlchemy.

    Warning: This method will overwrite existing attributes if they exists.

    :param exclude: Will be set as dictalchemy_exclude on the class
    :param exclude_underscore: Will be set as dictalchemy_exclude_underscore \
            on the class
    :param fromdict_allow_pk: Will be set as dictalchemy_fromdict_allow_pk\
            on the class
    :param asdict_include: Will be set as dictalchemy_asdict_include on the \
            class
    :param fromdict_include: Will be set as dictalchemy_fromdict_include on \
            the class

    :returns: The class
    """

    setattr(cls, 'dictalchemy_exclude', exclude)
    setattr(cls, 'dictalchemy_exclude_underscore', exclude_underscore)
    setattr(cls, 'dictalchemy_fromdict_allow_pk', fromdict_allow_pk)
    setattr(cls, 'asdict', asdict)
    setattr(cls, 'fromdict', fromdict)
    setattr(cls, '__iter__', iter)
    setattr(cls, 'dictalchemy_asdict_include', asdict_include)
    setattr(cls, 'dictalchemy_fromdict_include', fromdict_include)
    return cls