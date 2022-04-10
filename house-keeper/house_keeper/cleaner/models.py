from datetime import timedelta
from enum import Enum, IntEnum

from django.db import models


class ExtendedEnum(Enum):
    @classmethod
    def choices(cls):
        return tuple((i.value, i.name) for i in cls)


class ExtendedIntEnum(IntEnum):
    @classmethod
    def choices(cls):
        return ((i.value, i.name) for i in cls)


class Priority(ExtendedIntEnum):
    unessential = 5
    low = 4
    normal = 3
    high = 2
    critical = 1


class Category(models.Model):
    name = models.CharField(max_length=15, unique=True)


class Task(models.Model):
    title = models.CharField(max_length=100, unique=True, null=False)
    can_shift = models.BooleanField(default=True, null=False)
    priority = models.IntegerField(
        choices=Priority.choices(), default=Priority.low, null=False
    )
    category = models.ForeignKey(
        Category, default=1, on_delete=models.SET_DEFAULT  # "uncategorized
    )
    description = models.TextField(default=None, null=True, blank=True)
    duration_active = models.DurationField(null=False)
    duration_passive = models.DurationField(
        default=timedelta(minutes=0), null=False
    )
    frequency = models.DurationField(null=False)
    date_last_done = models.DateField(null=False)
