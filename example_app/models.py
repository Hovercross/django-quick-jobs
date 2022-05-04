"""Example app models, really only used for testing"""

from django.db import models


class Item(models.Model):
    key = models.CharField(max_length=256, unique=True)
    value = models.IntegerField()

    def __str__(self):
        return self.key
