import factory
import names
import random
from faker import Faker
from datetime import datetime, timedelta
from vtn.models import *
import string
from django.utils import timezone

fake = Faker()

'''
CUSTOMER MODEL 
    name = models.CharField('Name', db_index=True, max_length=100, unique=True)
    utility_id = models.CharField('Utility ID', max_length=100, unique=True)
    contact_name = models.CharField('Contact Name', max_length=100, blank=True)
    phone_number = models.CharField('Phone Number', max_length=13, null=True)
    '''


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'vtn.Customer'

    name = factory.LazyAttribute(lambda o: names.get_full_name())
    utility_id = factory.LazyAttribute(lambda o: random.randint(1000000, 9999999))
    contact_name = factory.LazyAttribute(lambda o: names.get_full_name())
    phone_number = factory.LazyAttribute(lambda o: random.randint(1000000000, 9999999999))


'''
SITE MODEL
    customer = models.ForeignKey(Customer)
    site_name = models.CharField('Site Name', max_length=100)
    site_id = models.CharField('Site ID', max_length=100)
    ven_id = models.CharField('VEN ID', max_length=100, unique=True, blank=True)
    ven_name = models.CharField('VEN Name', max_length=100, unique=True)
    site_location_code = models.CharField('Site Location Code', max_length=100)
    ip_address = models.CharField('IP address', max_length=100, blank=True)
    site_address1 = models.CharField('Address Line 1', max_length=100)
    site_address2 = models.CharField('Address Line 2', max_length=100, blank=True, null=True)
    city = models.CharField('City', max_length=100)
    state = models.CharField('State (abbr.)', max_length=2)
    zip = models.CharField('Zip', max_length=5)
    contact_name = models.CharField('Contact Name', max_length=100)
    phone_number = models.CharField('Phone Number', max_length=13)
    online = models.BooleanField(default=False)
    last_status_time = models.DateTimeField('Last Status Time', blank=True, null=True)
'''


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'vtn.Site'

    site_name = factory.LazyAttribute(lambda o: ''.join(fake.words(nb=2)))
    site_id = factory.Sequence(lambda n: 100 + n)
    site_location_code = factory.Sequence(lambda n: n)
    ip_address = factory.LazyAttribute(lambda n: fake.ipv4())
    ven_name = factory.Sequence(lambda n: "vtn{}".format(n))
    site_address1 = factory.LazyAttribute(lambda o: fake.street_address())
    city = factory.LazyAttribute(lambda o: fake.city())
    state = factory.LazyAttribute(lambda o: fake.state_abbr())
    zip = factory.LazyAttribute(lambda o: fake.zipcode())
    contact_name = factory.LazyAttribute(lambda o: names.get_full_name())
    phone_number = factory.LazyAttribute(lambda o: random.randint(100000000, 999999999))
    online = factory.LazyAttribute(lambda o: fake.boolean())
    reporting_status = factory.LazyAttribute(lambda o: fake.boolean())
    ven_id = factory.Sequence(lambda n: n)

    @factory.lazy_attribute
    def customer(self):
        customers = Customer.objects.all()
        return customers[random.randint(0, len(customers)-1)]

    @factory.lazy_attribute
    def last_status_time(self):
        return timezone.now()


'''
DR PROGRAM MODEL
    name = models.CharField('Program Name', max_length=100, unique=True)
    sites = models.ManyToManyField('Site', blank=True)
'''


class DRProgramFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'vtn.DRProgram'

    name = factory.Sequence(lambda n: "DR_Program_{}".format(n))


'''
#### DR EVENT MODEL #### 
    STATUS_CHOICES = (
        ('scheduled', 'scheduled'),
        ('far', 'far'),
        ('near', 'near'),
        ('active', 'active'),
        ('completed', 'completed'),
        ('cancelled', 'cancelled'),
        ('unresponded', 'unresponded')
    )

    dr_program = models.ForeignKey(DRProgram)
    scheduled_notification_time = models.DateTimeField('Scheduled Notification Time')
    start = models.DateTimeField('Event Start')
    end = models.DateTimeField('Event End')
    sites = models.ManyToManyField(Site, through='SiteEvent', related_name='Sites1')
    modification_number = models.IntegerField('Modification Number', default=0)
    status = models.CharField('Event Status', max_length=100, choices=STATUS_CHOICES, default='far')
    last_status_time = models.DateTimeField('Last Status Time', blank=True, null=True)
    superseded = models.BooleanField('Superseded', default=False)
    event_id = models.IntegerField('Event ID')
    deleted = models.BooleanField(default=False)
'''


class DREventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'vtn.DREvent'

    dr_program = factory.SubFactory(DRProgramFactory)
    # scheduled_notification_time = factory.LazyAttribute(lambda o: fake.date_time_between((datetime.now() -
    #                                                     timedelta(hours=2)), (datetime.now() + timedelta(hours=2))))
    scheduled_notification_time = factory.LazyAttribute(lambda o: timezone.now())
    # start = factory.LazyAttribute(lambda o: o.scheduled_notification_time + timedelta(hours=(random.randint(1, 3))))
    start = factory.LazyAttribute(lambda o: o.scheduled_notification_time + timedelta(seconds=10))
    end = factory.LazyAttribute(lambda obj: obj.start + timedelta(hours=random.randint(2, 5)))
    modification_number = 0
    last_status_time = factory.LazyAttribute(lambda obj: timezone.now())
    event_id = factory.Sequence(lambda n: n)
    superseded = False
    deleted = False

    @factory.lazy_attribute
    def status(self):
        if self.scheduled_notification_time > timezone.now():
            return 'active'
        elif self.scheduled_notification_time < timezone.now():
            return 'far'

    @factory.lazy_attribute
    def dr_program(self):
        programs = DRProgram.objects.all()
        return programs[random.randint(0, len(programs) - 1)]


# CREATE SITE EVENTS
choices = ['SCHEDULED', 'NOTIFICATION_SENT', 'ACTIVE',
           'COMPLETED', 'REPORTED', 'CANCELED',
           'ERROR']

dr_events = DREvent.objects.all()
sites = Site.objects.all()
opt_ins = [random.choice(['optIn', 'optOut', 'none']) for x in range(0, 50)]


# CREATE SITE EVENTS
for x in range(0, 50):  # Change range end for number of site events
    event = dr_events[random.randint(0, len(dr_events) - 1)]

    # Get the sites in the DR Program - don't make it random
    program = event.dr_program
    sites = program.sites.all()
    site = sites[random.randint(0, len(sites) - 1)]
    status = random.choice(choices)
    opt_in = fake.boolean()
    notification_time = event.scheduled_notification_time

    site_event = SiteEvent(dr_event=event,
                           status=status,
                           notification_sent_time=notification_time,
                           opt_in=opt_in,
                           site=site)
    site_event.save()

# CREATE TELEMETRY DATA FOR SITE EVENTS
site_events = SiteEvent.objects.all()

for site_event in site_events:
    dr_event = site_event.dr_event
    site = site_event.site

    start = dr_event.start
    end = dr_event.end

    fifteen_minute_increments = int(((end - start).seconds / 60) / 15)

    for x in range(0, fifteen_minute_increments):

        t = Telemetry()
        t.site = site

        t.created_on = start + timedelta(minutes=((x + 1) * 15))
        t.reported_on = start + timedelta(minutes=((x + 1) * 15))
        t.baseline_power_kw = random.randint(5, 20)
        t.measured_power_kw = random.randint(5, 20)
        t.baseline_energy_kwh = random.randint(5, 20)
        t.measured_energy_kwh = random.randint(5, 20)
        t.energy_kwh = random.randint(5, 20)

        t.save()
