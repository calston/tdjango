import datetime
import importlib

from twisted.internet import defer
from twisted.python import log
from twisted.enterprise import adbapi

from django.conf import settings
from django.db.models.base import ModelBase
from django.core.exceptions import ObjectDoesNotExist

from tdjango import db

class QueryAdapter(object):
    def __init__(self, name, model, manager):
        self._table = model._model._meta.db_table
        self._model = model
        self._manager = manager
        self._fields = model._fields

    def _get_field_list(self):
        fields = []
        foreign = []
        for k, v in self._fields.items():
            if v[0] == 'ForeignKey':
                fields.append('%s_id' % k)
                foreign.append(k)
            else:
                fields.append(k)

        return fields, foreign

    def delete(self, obj):
        return self._manager.delete(self._table, id=obj.id)

    #@defer.inlineCallbacks
    def insert(self, obj):
        fields, foreign = self._get_field_list()

        val = {}

        for f in fields:
            val[f] = getattr(obj, f)

        if foreign:
            for f in foreign:
                field_ref = getattr(obj, f)
                val['%s_id' % f] = field_ref.id

        del val['id']
        return self._manager.runInsert(self._table, val)

    #@defer.inlineCallbacks
    def update(self, obj):
        fields, foreign = self._get_field_list()

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
        m = self._model._model(**obj)
        
        m.save = self.insert
        
    @defer.inlineCallbacks
    def get(self, **kw):
        fields, foreign = self._get_field_list()

        obj = yield self._manager.selectOne(self._table, fields, **kw)

        if not obj:
            raise ObjectDoesNotExist()

        if foreign:
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

        m = self._model._model(**obj)

        m.delete = lambda: self.delete(m)
        m.save = lambda: self.update(m)

        defer.returnValue(m)

class ModelWrapper(object):
    def __init__(self, name, model_obj, manager):
        self._manager = manager
        self.name = name
        self._model = model_obj

        fields = self._model._meta.fields
        self._fields = {}
        for f in fields:
            self._fields[f.name] = (f.get_internal_type(), f)

        self.objects = QueryAdapter(name, self, manager)
    
class AbstractDjango(db.DBMixin):
    def __init__(self, app):
        self.models = {}

        settings.configure()

        self.modelmod = importlib.import_module('%s.models' % app)
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


