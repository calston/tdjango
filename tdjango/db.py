from twisted.internet import defer


class DBMixin(object):
    def _fetchOneTxn(self, txn, *a, **kw):
        " Transaction callback for self.fetchOne "
        txn.execute(*a)

        r = txn.fetchall()

        if r:
            return r[0]
        else:
            return None

    def fetchOne(self, *a, **kw):
        " Fetch one row only with this query "
        return self.p.runInteraction(self._fetchOneTxn, *a, **kw)

    
    def runInsert(self, table, keys):
        " Builds a simple INSERT statement"
        # Unzip the items tupple set into matched order k/v's
        keys, values = zip(*keys.items())

        st = "INSERT INTO %s (%s) VALUES (%s) RETURNING id" % (
            table,
            ','.join(keys),
            ','.join(['%s']*len(keys)) # Witchcraft
        )

        return self.fetchOne(st, values)

    def runUpdate(self, table, keys, **constraints):
        " Builds a simple UPDATE statement"
        setkeys, setvalues = zip(*keys.items())
        ckeys, cvalues = zip(*constraints.items())

        st = "UPDATE %s SET %s" % (
            table,
            ','.join(['%s=%%s' % (k) for k in setkeys])
        )

        if ckeys:
            st += " WHERE %s" % (' AND '.join(['%s=%%s' % (k) for k in ckeys]))

        return self.p.runOperation(st, setvalues + cvalues)

    def delete(self, table, **constraints):
        st = 'DELETE FROM %s ' % table

        ckeys, cvalues = zip(*constraints.items())
        if ckeys:
            st += " WHERE %s" % (' AND '.join(['%s=%%s' % (k) for k in ckeys]))
        
        return self.p.runOperation(st, cvalues)

    @defer.inlineCallbacks
    def select(self, table, fields, **kw):
        q = []
        args = []
        for k, v in kw.items():
            q.append('%s=%%%%s' % k)
            args.append(v)

        query = "SELECT %s FROM %s" 

        if q:
            query += " WHERE " + ' and '.join(q)

        results = yield self.p.runQuery(query % (
                ','.join(fields),
                table,
            ), tuple(args))

        res = []

        for r in results:
            obj = {}
            for i, col in enumerate(r):
                obj[fields[i]] = col

            res.append(obj)

        defer.returnValue(res)

    @defer.inlineCallbacks
    def selectOne(self, *a, **kw):
        r = yield self.select(*a, **kw)
        if r:
            defer.returnValue(r[0])
        else:
            defer.returnValue(None)

