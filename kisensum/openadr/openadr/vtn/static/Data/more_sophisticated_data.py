import random
from datetime import datetime, timedelta
from vtn.models import *
from django.db.models import Q

# ------------------------------ Test Distribute Event and Created Event ------------------------------ #
"""
I will assume DR Programs are already set-up in the database
"""

dr_programs = DRProgram.objects.filter(~Q(sites=None))

"""
I will create events whose notification time is about to happen,
but won't be completed for about a day
"""

# Create 5 events
for x in range(0, 5):
    dr_program = dr_programs[random.randint(0, len(dr_programs) - 1)]
    sites_in_program = dr_program.sites.all()
    site = sites_in_program[random.randint(0, len(sites_in_program) - 1)]
    events = DREvent.objects.all().order_by('-event_id')
    try:
        event_id = events[0].event_id + 1
    except IndexError:
        event_id = 0

    now = datetime.now()
    event_notification = now + timedelta(minutes=1)
    event_start = now + timedelta(days=1)
    event_end = now + timedelta(days=2)
    event = DREvent(dr_program=dr_program,
                    scheduled_notification_time=event_notification,
                    start=event_start,
                    end=event_end,
                    modification_number=0,
                    status='far',
                    previous_version=None,
                    superseded=False,
                    event_id=event_id,
                    deleted=False)

    event.save()

    # We have a site at this point
    s = SiteEvent(dr_event=event,
                  status='far',
                  last_status_time=datetime.now(),
                  site=site)
    s.save()
# ------------------------------ End Distribute Event and Created Event ------------------------------ #



