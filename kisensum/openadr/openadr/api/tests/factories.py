import factory
import names
import random
from faker import Faker
from datetime import datetime, timedelta
from vtn.models import *
import string
from django.utils import timezone
import logging

# This is necessary or else DEBUG statements for FactoryBoy will be sent to output
logging.getLogger("factory").setLevel(logging.WARN)

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

    @factory.lazy_attribute
    def customer(self):
        customers = Customer.objects.all()
        return customers[random.randint(0, len(customers)-1)]

    @factory.lazy_attribute
    def last_status_time(self):
        return timezone.now()

    @factory.lazy_attribute
    def ven_id(self):
        all_sites = [int(s.ven_id) for s in Site.objects.all()]
        all_sites.sort()
        ven_id = str(all_sites[-1] + 1) if len(all_sites) > 0 else '0'
        return ven_id


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
    scheduled_notification_time = factory.LazyAttribute(lambda o: timezone.now())
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


