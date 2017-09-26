import factory
import names
import random
from faker import Faker
from datetime import datetime, timedelta
from vtn.models import *
import string

fake = Faker()


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'vtn.Customer'

    name = factory.LazyAttribute(lambda o: names.get_full_name())
    utility_id = factory.LazyAttribute(lambda o: random.randint(1000000, 9999999))
    contact_name = factory.LazyAttribute(lambda o: names.get_full_name())
    phone_number = factory.LazyAttribute(lambda o: random.randint(1000000000, 9999999999))


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'vtn.Site'

    site_name = factory.LazyAttribute(lambda o: ''.join(fake.words(nb=2)))
    site_id = factory.Sequence(lambda n: 100 + n)
    site_location_code = factory.Sequence(lambda n: 200 + n)
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

    @factory.lazy_attribute
    def customer(self):
        customers = Customer.objects.all()
        return customers[random.randint(0, len(customers)-1)]


    @factory.lazy_attribute
    def ven_id(self):
        # example = '919a1dfa088fe14b79f9'
        # pattern = 100-999 + letter + 1-10 + three letters + 0 + 10-99 + two letters + 10-99 + letter
        # + 10-99 + letter + 1-9
        letters = string.ascii_lowercase
        return (str(random.randint(100, 999)) +
               random.choice(letters) +
               str(random.randint(1, 9)) +
               random.choice(letters) + random.choice(letters) + random.choice(letters) +
               str(0) +
               str(random.randint(10, 99)) +
               random.choice(letters) + random.choice(letters) +
               str(random.randint(10, 99)) +
               random.choice(letters))


class DRProgramFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'vtn.DRProgram'

    name = factory.Sequence(lambda n: "drprogram{}".format(n))


# ENROLL SITES IN DR PROGRAMS
programs = DRProgram.objects.all()

sites = Site.objects.all()

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
# END ENROLL SITES IN DR PROGRAMS


class DREventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'vtn.DREvent'

    dr_program = factory.SubFactory(DRProgramFactory)
    scheduled_notification_time = factory.LazyAttribute(lambda o: fake.date_time_between((datetime.now() -
                                                        timedelta(hours=2)), (datetime.now() + timedelta(hours=2))))
    start = factory.LazyAttribute(lambda o: o.scheduled_notification_time + timedelta(hours=(random.randint(1, 3))))
    end = factory.LazyAttribute(lambda obj: obj.start + timedelta(hours=random.randint(2, 5)))
    modification_number = 0
    last_status_time = factory.LazyAttribute(lambda obj: datetime.now())
    event_id = factory.Sequence(lambda n: n)

    @factory.lazy_attribute
    def status(self):
        if self.scheduled_notification_time > datetime.now():
            return 'SCHEDULED'
        elif (self.scheduled_notification_time < datetime.now()) and self.start > datetime.now():
            return 'NOTIFICATION_SENT'
        elif (self.start < datetime.now()) and self.end > datetime.now():
            return 'ACTIVE'
        else:
            return 'COMPLETED'

    @factory.lazy_attribute
    def dr_program(self):
        programs = DRProgram.objects.all()
        return programs[random.randint(0, len(programs) - 1)]


# CREATE CUSTOMERS
CustomerFactory.create_batch(20)

# CREATE SITES
SiteFactory.create_batch(60)

# CREATE DR PROGRAMS
# DRProgramFactory.create_batch(5)

# CREATE DR EVENTS
DREventFactory.create_batch(15)


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
