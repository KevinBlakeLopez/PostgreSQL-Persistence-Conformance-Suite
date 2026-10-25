"""Unmanaged Django models over the SQLITE-01 tables (the study creates them with raw SQL)."""

from django.db import models


class Account(models.Model):
    balance = models.IntegerField()

    class Meta:
        db_table = "accounts"
        managed = False


class Ledger(models.Model):
    token = models.TextField()
    step = models.TextField()

    class Meta:
        db_table = "ledger"
        managed = False
