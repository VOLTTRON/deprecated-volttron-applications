# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-11-20 15:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vtn', '0036_auto_20171120_1545'),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_request_id', models.CharField(blank=True, max_length=100, null=True)),
            ],
        ),
    ]