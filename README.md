# tDjango

The 'D' is silent. 

tDjango is a wrapper which allows Django ORM models to be used in Twisted with relative ease.
ONLY Postgres is supported, and it does not implement the full query language.

## Usage

```python
from tdjango import DjangoORM
from twisted.internet import reactor

@defer.inlineCallbacks
def main():

    mydb = DjangoORM('mydjangoapp')

    # Creating and retrieving objects works mostly the same
    red_pencil = mydb.Pencil.objects.create(colour='red')
    yield red_pencil.save()

    green_pencil = mydb.Pencil.objects.create(colour='green')
    yield green_pencil.save()

    apencil = yield mydb.Pencil.objects.get(color='red')


    # .all() is a synonym for .filter(), which supports the same syntax as get
    # but only some queries (__gte, __lte, __lt, etc) but not chained queries
    mypencils = yield mydb.Pencil.objects.all()

    # ForeignKey and ManyToMany work (mostly) as expected
    pencilcase = mydb.PencilCase.objects.create()
    yield pencilcase.save()

    yield pencilcase.pencils.set(mypencils)

    # Get related sets
    yield green_pencil.pencilcase_set.all()

    # And lastly you can delete things
    yield pencilcase.delete()
    yield red_pencil.delete()

    reactor.stop()

reactor.callWhenRunning(main)
reactor.run()
```

