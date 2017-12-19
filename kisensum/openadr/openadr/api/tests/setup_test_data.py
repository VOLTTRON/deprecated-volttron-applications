from vtn.models import *
from . import factories as factory
import random
from django.utils import timezone


def create_dr_programs(num_programs):
    factory.DRProgramFactory.create_batch(num_programs)


def create_customers(num_customers):
    factory.CustomerFactory.create_batch(num_customers)


def create_sites(num_sites):
    factory.SiteFactory.create_batch(num_sites)
    sites = Site.objects.all()
    programs = DRProgram.objects.all()
    for site in sites:
        program = programs[random.randint(0, len(programs) - 1)]
        program.sites.add(site)
        program.save()
        program = programs[random.randint(0, len(programs) - 1)]
        program.sites.add(site)
        program.save()
        program = programs[random.randint(0, len(programs) - 1)]
        program.sites.add(site)
        program.save()


'''
SITE EVENT MODEL
    STATUS_CHOICES = (
        ('scheduled', 'scheduled'),
        ('far', 'far'),
        ('near', 'near'),
        ('active', 'active'),
        ('completed', 'completed'),
        ('cancelled', 'cancelled'),
        ('unresponded', 'unresponded')
    )
    OPT_IN_CHOICES = (
        ('optIn', 'optIn'),
        ('optOut', 'optOut'),
        ('none', 'Neither')
    )
    VEN_STATUS_CHOICES = (
        ('not_told', 'not_told'),
        ('told', 'told'),
        ('acknowledged', 'acknowledged')
    )
    dr_event = models.ForeignKey(DREvent)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default='scheduled')
    notification_sent_time = models.DateTimeField('Notification Sent Time', blank=True, null=True)
    last_status_time = models.DateTimeField('Last Status Time')
    modification_number = models.IntegerField('Modification Number', default=0)
    opt_in = models.CharField(max_length=100, choices=OPT_IN_CHOICES, default='none')
    ven_status = models.CharField(max_length=100, choices=VEN_STATUS_CHOICES, default='not_told')
    last_opt_in = models.DateTimeField('Last opt-in', blank=True, null=True)
    site = models.ForeignKey(Site)
    previous_version = models.ForeignKey('self', blank=True, null=True)
    deleted = models.BooleanField(default=False)
'''


# This function also creates site_events
def create_dr_events(num_dr_events):
    factory.DREventFactory.create_batch(num_dr_events)
    dr_events = DREvent.objects.all()

    for dr_event in dr_events:
        program = dr_event.dr_program
        sites = program.sites.all()
        site = sites[random.randint(0, len(sites) - 1)]
        status = 'far'
        modification_number = 0
        opt_in = 'none'
        ven_status = 'not_told'
        deleted = False

        site_event = SiteEvent(dr_event=dr_event,
                               site=site,
                               status=status,
                               modification_number=modification_number,
                               opt_in=opt_in,
                               ven_status=ven_status,
                               deleted=deleted,
                               last_status_time=timezone.now())
        site_event.save()
