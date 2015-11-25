from django.db import models

from django.contrib.auth.models import User

class Color(models.Model):
    color = models.CharField(max_length=255)
    r, g, b = (models.IntegerField(default=0), models.IntegerField(default=0),
        models.IntegerField(default=0))

class Animals(models.Model):
    name = models.CharField(max_length=255, unique=True)
    weight = models.IntegerField()
    owner = models.ForeignKey(User, blank=True)
    
    color = models.ForeignKey(Color)

class Rainbows(models.Model):
    name = models.CharField(max_length=255, unique=True)
    colors = models.ManyToManyField(Color)

