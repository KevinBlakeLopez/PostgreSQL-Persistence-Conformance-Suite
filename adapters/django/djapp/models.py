from django.db import models


class Item(models.Model):
    name = models.TextField()
    qty = models.IntegerField(default=0)

    class Meta:
        app_label = "djapp"
        db_table = "item"


class Uniq(models.Model):
    code = models.TextField(unique=True)

    class Meta:
        app_label = "djapp"
        db_table = "uniq"
