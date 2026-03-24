"""
Theeeme model for OIUEEI.
"""

from django.db import models

from core.utils import generate_id


class Theeeme(models.Model):
    """
    A color palette theme for collections.
    Colors are HDS token names (e.g. "bus", "copper", "suomenlinna-light").
    """

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    name = models.CharField(max_length=16, default="")
    color_01 = models.CharField(max_length=32)
    color_02 = models.CharField(max_length=32)
    color_03 = models.CharField(max_length=32)
    color_04 = models.CharField(max_length=32)
    color_05 = models.CharField(max_length=32)

    class Meta:
        app_label = "core"
        db_table = "theeemes"

    def __str__(self):
        return self.code
