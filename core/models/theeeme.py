"""
Theeeme model for OIUEEI.
"""

from django.db import models

from core.utils import generate_id


class Theeeme(models.Model):
    """
    A color palette theme for collections.
    Contains 6 color values (hex codes without #).
    """

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    name = models.CharField(max_length=16)
    color_01 = models.CharField(max_length=6)
    color_02 = models.CharField(max_length=6)
    color_03 = models.CharField(max_length=6)
    color_04 = models.CharField(max_length=6)
    color_05 = models.CharField(max_length=6)
    color_06 = models.CharField(max_length=6)

    class Meta:
        app_label = "core"
        db_table = "theeemes"

    def __str__(self):
        return f"{self.code}: {self.name}"
