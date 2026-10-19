from tortoise import fields
from tortoise.models import Model


class Item(Model):
    id = fields.IntField(primary_key=True, generated=True)
    name = fields.TextField()
    qty = fields.IntField()

    class Meta:
        table = "item"


class Uniq(Model):
    id = fields.IntField(primary_key=True, generated=True)
    code = fields.CharField(max_length=255, unique=True)

    class Meta:
        table = "uniq"
