from twisted.trial import unittest

from twisted.internet import defer, reactor, error
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol

from tdjango import DjangoORM

class Test(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.db = DjangoORM('tdjango.tests.testapp')

        yield self.db.delete('testapp_rainbows_colors')
        yield self.db.delete('testapp_rainbows')
        yield self.db.delete('testapp_animals')
        yield self.db.delete('testapp_color')
        yield self.db.delete('auth_user')

        self.red = self.db.Color.objects.create(
            color='red', 
            r=255
        )
        yield self.red.save()

        self.blue = yield self.db.Color.objects.create(
            color='blue', 
            b=255
        )
        yield self.blue.save()

        self.john = self.db.User.objects.create(
            username='john'
        )
        yield self.john.save()

        elephant = self.db.Animals.objects.create(
            name='Blue elephant',
            weight=10000,
            owner=self.john,
            color=self.blue
        )

        yield elephant.save()

        self.rainbow_rb = self.db.Rainbows.objects.create(
            name='rg'
        )

        yield self.rainbow_rb.save()

        yield self.rainbow_rb.colors.add(self.red)
        yield self.rainbow_rb.colors.add(self.blue)


    @defer.inlineCallbacks
    def tearDown(self):
        # Truncate all the tables
        yield self.db.delete('testapp_rainbows_colors')
        yield self.db.delete('testapp_rainbows')
        yield self.db.delete('testapp_animals')
        yield self.db.delete('testapp_color')
        yield self.db.delete('auth_user')

    def test_adapter(self):
        self.assertIn('Color', self.db.models)
        self.assertIn('Animals', self.db.models)
        self.assertIn('User', self.db.models)
        
    @defer.inlineCallbacks
    def test_create(self):
        model = self.db.Color.objects.create(
            color='green', 
            g=255
        )

        self.assertEquals(model.g, 255)
        self.assertEquals(model.color, 'green')

        yield model.save()

        m2 = yield self.db.Color.objects.get(color='green')
        self.assertEquals(m2.g, 255)
        self.assertEquals(m2.r, 0)
    
    @defer.inlineCallbacks
    def test_update(self):
        blue = yield self.db.Color.objects.get(color='blue')

        blue.g = 30

        yield blue.save()

        blue = yield self.db.Color.objects.get(color='blue')

        self.assertEquals(blue.g, 30)
        self.assertEquals(blue.b, 255)
        self.assertEquals(blue.r, 0)

    @defer.inlineCallbacks
    def test_relations(self):
        snake = self.db.Animals.objects.create(
            name='Red snake',
            weight=1,
            owner=self.john,
            color=self.red
        )

        yield snake.save()

        id = snake.id

        mysnake = yield self.db.Animals.objects.get(name='Red snake')
        
        self.assertEquals(mysnake.id, id)
        self.assertEquals(mysnake.owner, self.john)
        self.assertEquals(mysnake.color, red)
        self.assertEquals(mysnake.color.id, red.id)
        self.assertEquals(mysnake.color.r, 255)

    @defer.inlineCallbacks
    def test_manymany(self):
        red = yield self.db.Color.objects.get(color='red')
        blue = yield self.db.Color.objects.get(color='blue')
        green = self.db.Color.objects.create(
            color='green', 
            g=255
        )
        yield green.save()

        rainbow = self.db.Rainbows.objects.create(
            name='rgb'
        )

        yield rainbow.save()

        yield rainbow.colors.add(red)

        self.assertIn(red, rainbow.colors)

        yield rainbow.colors.set([green, blue])

        yield rainbow.save()

        rain2 = yield self.db.Rainbows.objects.get(name='rgb')

        self.assertIn(green, rain2.colors)
        self.assertIn(blue, rain2.colors)

        yield rain2.delete()
        
    @defer.inlineCallbacks
    def test_objects_filter(self):
        colors = yield self.db.Color.objects.filter(color='red')

        red = yield self.db.Color.objects.get(color='red')
        self.assertIn(red, colors)

    @defer.inlineCallbacks
    def test_objects_all(self):
        colors = yield self.db.Color.objects.all()

        red = yield self.db.Color.objects.get(color='red')
        self.assertIn(red, colors)


    @defer.inlineCallbacks
    def test_foreign_get(self):
        blue = yield self.db.Color.objects.get(color='blue')

        elephant = yield self.db.Animals.objects.get(color=blue)

        self.assertEquals(elephant.name, "Blue elephant")

        elephants = yield self.db.Animals.objects.filter(color=blue)

        self.assertEquals(elephants[0].name, "Blue elephant")

    @defer.inlineCallbacks
    def test_set_reverse_query(self):
        # Single foreign key
        elephants = yield self.blue.animals_set.all()

        self.assertEquals(elephants[0].name, "Blue elephant")

        # ManyToMany keys

        rainbows = yield self.blue.rainbows_set.all()

        self.assertEquals(rainbows[0].name, 'rg')

