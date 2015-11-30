import datetime
import importlib

from twisted.internet import defer
from twisted.python import log
from twisted.enterprise import adbapi

from django.conf import settings
from django.db.models.base import ModelBase
from django.core.exceptions import ObjectDoesNotExist

from tdjango import db

settings.configure()

class ManyManyProxy(list):
    def __init__(self, query_adapter, parent, field):
        self.query_adapter = query_adapter
        self.field = field
        self.parent = parent

    def set(self, items):
        return self.query_adapter.m2m_set(self.parent, self.field, items)

    def add(self, item):
        return self.query_adapter.m2m_add(self.parent, self.field, item)

class QueryAdapter(object):
    def __init__(self, name, model, manager):
        self._name = name
        self._table = model._model._meta.db_table
        self._model = model
        self._manager = manager
        self._fields = model._fields

    def _get_field_list(self):
        fields = []
        foreign = []
        many = []
        for k, v in self._fields.items():
            if v[0] == 'ForeignKey':
                fields.append('%s_id' % k)
                foreign.append(k)
            elif v[0] == 'ManyToManyField':
                many.append(k)
            else:
                fields.append(k)

        return fields, foreign, many

    def _bind_many(self, obj, many):
        for f in many:
            setattr(obj, f, ManyManyProxy(self, obj, f))

    @defer.inlineCallbacks
    def delete(self, obj):
        fields, foreign, many = self._get_field_list()
        
        for m in many:
            yield self.m2m_set(obj, m, [])

        yield self._manager.delete(self._table, id=obj.id)

    @defer.inlineCallbacks
    def insert(self, obj):
        fields, foreign, many = self._get_field_list()

        val = {}

        for f in fields:
            val[f] = getattr(obj, f)

        if foreign:
            for f in foreign:
                field_ref = getattr(obj, f)
                if field_ref:
                    val['%s_id' % f] = field_ref.id

        print val, fields, foreign, many

        del val['id']
        
        id = yield self._manager.runInsert(self._table, val)

        obj.id = id[0]

        obj.delete = lambda: self.delete(obj)
        obj.save = lambda: self.update(obj)

        self._bind_many(obj, many)

        defer.returnValue(obj)

    #@defer.inlineCallbacks
    def update(self, obj):
        fields, foreign, many = self._get_field_list()

        val = {}

        for f in fields:
            val[f] = getattr(obj, f)

        if foreign:
            for f in foreign:
                field_ref = getattr(obj, f)
                val['%s_id' % f] = field_ref.id

        del val['id']
        
        return self._manager.runUpdate(self._table, val, id=obj.id)
       
    def create(self, **kw):
        fields, foreign, many = self._get_field_list()
        
        m = self._model._model(**kw)

        m.save = lambda: self.insert(m)

        return m

    def _get_m2m_schema(self, field):
        field_obj = self._fields[field][1]
        m2m_table = field_obj.m2m_db_table()

        dst_name = '%s_id' % field_obj.related.to.__name__.lower()
        src_name = '%s_id' % self._name.lower() 

        return m2m_table, dst_name, src_name

    @defer.inlineCallbacks
    def m2m_set(self, parent, field, items):
        m2m_table, dst_name, src_name = self._get_m2m_schema(field)


        # Erase existing items
        yield self._manager.delete(m2m_table,
            **{src_name: parent.id})

        # Wipe the field meta list
        del getattr(parent, field)[:]

        for item in items:
            yield self.m2m_add(parent, field, item)

    @defer.inlineCallbacks
    def m2m_add(self, parent, field, item):
        "Add `item` to many-to-many relationship"

        m2m_table, dst_name, src_name = self._get_m2m_schema(field)

        yield self._manager.runInsert(m2m_table,
            {dst_name: item.id, src_name: parent.id})

        getattr(parent, field).append(item)


    @defer.inlineCallbacks
    def _resolve_object(self, obj, fields, foreign, many):
        # Resolve foreign keys recursively
        for f in foreign:
            field_ref = self._fields[f][1]
            
            ref_id = obj['%s_id' % f]
            del obj['%s_id' % f]

            if ref_id:
                field_name = field_ref.related.to.__name__
                field = self._manager.models.get(field_name)

                if field:
                    obj[f] = yield field.objects.get(id=ref_id)
            else:
                obj[f] = None

        # Construct Django model
        m = self._model._model(**obj)

        # Resolve many to many relations
        self._bind_many(m, many)

        for f in many:
            m2m_table, dst_name, src_name = self._get_m2m_schema(f)

            objects = yield self._manager.select(m2m_table,
                [src_name, dst_name], **{src_name: obj['id']})

            model_name = self._fields[f][1].related.to.__name__

            model_ref = self._manager.models.get(model_name)

            if model_ref:
                for m2mobj in objects:
                    item = yield model_ref.objects.get(id=m2mobj[dst_name])
                    getattr(m, f).append(item)
            else:
                # XXX We need to push unreferenced models back to the manager
                pass

        m.delete = lambda: self.delete(m)
        m.save = lambda: self.update(m)

        defer.returnValue(m)

    def _remap_foreign(self, foreign, d):
        # Re-map foreign where clauses
        for f in foreign:
            if f in d:
                id = d[f].id
                del d[f]
                d['%s_id' % f] = id
       
    @defer.inlineCallbacks
    def get(self, **kw):
        fields, foreign, many = self._get_field_list()

        self._remap_foreign(foreign, kw)

        obj = yield self._manager.selectOne(self._table, fields, **kw)

        if not obj:
            raise ObjectDoesNotExist()

        m = yield self._resolve_object(obj, fields, foreign, many)

        defer.returnValue(m)

    @defer.inlineCallbacks
    def filter(self, **kw):
        fields, foreign, many = self._get_field_list()

        self._remap_foreign(foreign, kw)

        objs = yield self._manager.select(self._table, fields, **kw)

        obj_list = []

        for obj in objs:
            m = yield self._resolve_object(obj, fields, foreign, many)
            obj_list.append(m)

        defer.returnValue(obj_list)

    def all(self):
        return self.filter()

class ModelWrapper(object):
    def __init__(self, name, model_obj, manager):
        self._manager = manager
        self.name = name
        self._model = model_obj

        fields = self._model._meta.fields
        self._fields = {}

        # Yank out model fields
        for f in fields:
            self._fields[f.name] = (f.get_internal_type(), f)

        # Many to many fields are stored separately
        if self._model._meta.many_to_many:
            for f in self._model._meta.many_to_many:
                self._fields[f.name] = (f.get_internal_type(), f)

                # Snap off the crazy Django relation manager
                setattr(self._model, f.name, [])

        self.objects = QueryAdapter(name, self, manager)
    
class AbstractDjango(db.DBMixin):
    def __init__(self, app, settings=None):
        self.models = {}

        self.modelmod = importlib.import_module('%s.models' % app)

        if settings:
            app_settings = importlib.import_module(settings)
        else:
            app_settings = importlib.import_module('%s.settings' % app)

        db_name = app_settings.DATABASES['default']['NAME']
        db_host = app_settings.DATABASES['default'].get('HOST', 'localhost')
        db_user = app_settings.DATABASES['default'].get('USER', 'postgres')
        db_pass = app_settings.DATABASES['default'].get('PASSWORD', None)
        db_port = app_settings.DATABASES['default'].get('PORT', 5432)

        self.p = adbapi.ConnectionPool('psycopg2',
            database=db_name,
            host=db_host,
            user=db_user,
            password=db_pass,
            port=db_port
        )

        self.loadModel()

    def loadModel(self):
        "Load models.* for this application into a dict"

        for attr in dir(self.modelmod):
            a = getattr(self.modelmod, attr)
            if a.__class__ is ModelBase:
                self.models[attr] = ModelWrapper(attr, a, self)

    def __getattribute__(self, attr):
        "This is pretty inefficient, but that's a future issue" 
        if attr != 'models':
            if attr in self.models:
                return self.models[attr]
            
        return object.__getattribute__(self, attr)


