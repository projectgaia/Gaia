#!/usr/bin/env python

##########################################################################
#  
#  Gaia, task list organiser in with Caldav server sync.
#  
#  Copyright (C) 2013-2014 Dr Adam S. Candy.
#  Dr Adam S. Candy, contact@gaiaproject.org
#  
# This file is part of the Gaia project.
# 
# Gaia is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Gaia is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Gaia.  If not, see <http://www.gnu.org/licenses/>.
#
##########################################################################

from Universe import universe, colour
import sys
import os

from Support import error, report
from Support import generate_mono
from Support import repo_update, repo_add
from Parsers import prioritystring, is_same_time, timedelta_to_human, urlbasename

def calendar_load(calendarname, principalurl=None, forced=False):
  from caldav import DAVClient, Principal
  from caldav.elements import dav, cdav
  if principalurl is None:
    principalurl = universe.principalurl
  valid = False
  if 'CLIENT' in universe.calendarcache.keys():
    client = universe.calendarcache['CLIENT']
    if (calendarname in universe.calendarcache.keys() and not forced):
      calendar = universe.calendarcache[calendarname]
      if calendarname == 'CLIENT':
        valid = True
      else:
        try:
          calendar.events()
          valid = True
        except:
          valid = False
          pass
  #report(calendarname + ' ' + str(valid))
  if not valid: 
    client = DAVClient(principalurl)
    universe.calendarcache['CLIENT'] = client
    principal = Principal(client, principalurl)
    calendars = principal.calendars()
    report(colour.blue + 'Updating calendar sockets' + colour.end, routine=True)
    for calendar in calendars:
      props = calendar.get_properties([dav.DisplayName()])
      #props = calendar.get_properties([dav.DisplayName(), dav.Status(), dav.Href()])
      name = props['{DAV:}displayname'].lower()
      #href = props['{DAV:}href']
      universe.calendarcache[name] = calendar
      address = urlbasename(calendar.url.path)
      universe.calendaraddresstoname[address] = name
      #print name, address
  return client, calendar

# http://sabre.io/dav/building-a-caldav-client/
# https://github.com/dengste/org-caldav/blob/master/org-caldav.el
# http://blogs.nologin.es/rickyepoderi/index.php?/archives/15-Introducing-CalDAV-Part-II.html

# https://github.com/technosophos/SabreDAV
# https://github.com/gggard/AndroidCaldavSyncAdapater/issues/86

def calendar_ctag(debug=False):
  changed = False
  xml = """<?xml version="1.0" encoding="UTF-8"?>
<D:propfind xmlns:D="DAV:" xmlns:CS="http://calendarserver.org/ns/" xmlns:C="urn:ietf:params:xml:ns:caldav">
<D:prop>
<CS:getctag/>
</D:prop>
</D:propfind>"""
  ok = False
  attempt = 0
  while True:
    attempt += 1
    if attempt > 3:
      break
    if attempt > 1:
      client, calendar = calendar_load('CLIENT', forced=True)
    else:
      client, calendar = calendar_load('CLIENT')
    try:
      d = client.propfind(url=universe.principalurl, props=xml, depth=1)
      if debug:
        print d.raw
      for i in range(len(d.tree)):
        address = d.tree[i][0].text
        base = urlbasename(d.tree[i][0].text)
        if base not in universe.calendaraddresstoname:
          continue
        ctag = d.tree[i][1][0][0].text
        if debug:
          name = universe.calendaraddresstoname[base]
          print i, name, base, ctag
        if base not in universe.calendarctag.keys():
          universe.calendarctag[base] = ctag
        elif universe.calendarctag[base] != ctag:
          changed = True
          universe.calendarctag[base] = ctag
      ok = True
      break
    except Exception, e:
      #error('Failed to read ctags on attempt %(attempt)d, exception: %(error)s' % {'attempt':attempt, 'error':str(e)})
      ##raise
      pass
  if not ok:
    error('Failed to read ctags on all attempts')
  return changed

def calendar_backup(principalurl=None):
  ok = True
  client, calendar = calendar_load('', principalurl=principalurl)
  report((colour.blue + 'Backup of '+colour.yellow+'%s'+colour.blue+' calendars: ' + colour.end) % str(len(universe.calendarcache) - 1))
  for calendarname in universe.calendarcache.keys():
    if calendarname == 'CLIENT': continue
    report(colour.blue + 'Calendar: ' + colour.end + calendarname)
    out = ''
    filename = universe.backuproot + calendarname + '.ics'
    client, calendar = calendar_load(calendarname, principalurl=principalurl)
    entries = 0
    for event in calendar.events():
      event.load()
      e = event.get_data().decode('utf-8')
      if e is not None:
        entries += 1
        out = out + e + os.linesep
      else:
        report(colour.red+'  error: event is None in ' + calendarname + colour.end)
        ok = False
      # asc - for testing:
      #if entries > 2: break
    report((colour.blue + '  writing out '+colour.yellowbright+'%(entries)s'+colour.blue+' entries to '+colour.yellow+'%(calendarname)s'+colour.end) % {'entries':entries, 'calendarname':calendarname})
    try:
      f = open(filename.encode('utf-8'), 'w')
      out = out.replace('\r','')
      f.write(out.encode('utf-8'))
      f.close()
      repo_add(filename, prefix='  ')
    except Exception, e:
      ok = False
      report(colour.red+'  error: in writing and adding to repo ' + calendarname + colour.end + ' Exception: ' + str(e))
      pass
  try:
    repo_update(commit=True, root=universe.backuproot)
  except Exception, e:
    if universe.debug: raise
    report(colour.red+'  error: in repo update and commit' + colour.end + ' Exception: ' + str(e))
    ok = False
    pass
  return ok

def calendars_clear(calendarnames):
  for calendarname in calendarnames:
    client, calendar = calendar_load(calendarname)
    for calendarevent in calendar.events():
      report(colour.red + 'Removed unexpected event in calendar: ' + calendarname + colour.end)
      calendarevent.delete()

def ical_event_delete(task, name=None):
  from icalendar import Calendar
  # Note removes duplicates
  if name is None:
    name = task.name
  calendarname = task.group()
  stat = False
  client, calendar = calendar_load(calendarname)
  events = calendar.events()
  for event in events:
    if str(event).endswith('/'): continue
    try:
      event.load()
    except:
      error('Failed to load caldav event: ' + name)
      continue
    data = Calendar().from_ical(event.get_data())
    for component in data.walk():
      if component.name == "VTODO":
        if component.get('summary') == name:
          if not universe.dry:
            event.delete()
          report(colour.red + '  removed caldav event: ' + name + ' (calendar: ' + calendarname + ')' + colour.end)
          stat = True
  return stat

def ical_event_add(task):
  name = task.name
  # Extra to *really* ensure event doesn't already exist in caldav
  if ical_event_delete(task):
    error('Needed to remove an event from caldav to make way for a new addition of the same name: ' + name + ' [SHOULD NOT BE HERE!]')
  calendarname = task.group()
  client, calendar = calendar_load(calendarname)
  added = task_add(client, calendar, task)
  stat = added is not None
  if stat:
    report(colour.green + '  added caldav event: ' + name + ' (calendar: ' + calendarname + ')' + colour.end)
  else:
    error('could not add caldav event: ' + name)
  return stat

def ical_event_update(task, due=False, note=False, priority=False, wait=False, translate=False, previous=None, next_action=True):
  from icalendar import Calendar
  if (wait or translate):
    # Special case, needs removal then addition
    # TODO
    if previous is None:
      error('ical_event_update requires previous!')
      return False
    stat_remove = ical_event_delete(previous)
    stat_add = ical_event_add(task)
    stat = stat_remove and stat_add
    return stat

  if len(task.titleoptions) > 0:
    name = task.name + '  ' + task.titleoptions
  else:
    name = task.name
  calendarname = task.group()
  stat = False
  client, calendar = calendar_load(calendarname)
  events = calendar.events()

  todo = None
  alarm = None

  for event in events:
    valid = False
    if str(event).endswith('/'): continue
    try:
      event.load()
    except:
      error('Failed to load caldav event: ' + name)
      continue
    data = Calendar().from_ical(event.get_data())
    for component in data.walk():
      if component.name == "VTODO":
        if component.get('summary') == name:
          valid = True
          todo = component
      elif component.name == "VALARM":
        if valid:
          if component.get('acknowledged') is None:
            alarm = component
    if valid:
      # Keep hold of event
      break

  # Note 'alarm' now not used, generate a new vcal object with the same uid, incremented sequence
  if todo is not None:
    task.sequence += 1
    #print task.next_action
    vcal = task_create(task=task, uid=task.uid)
    #print vcal
    if vcal is None:
      stat = False
    else:
      if universe.dry:
        stat = True
      else:
        try:
          event.data = vcal
          ev = event.save()
          stat = True
          #print task.next_action
          #print vcal
          report(colour.yellow + '  updated caldav event: ' + task.name + colour.end)
        except:
          stat = False
          error('Update of caldav, event save failed ' + task.name)
          pass
  else:
    error('Update of caldav, not found, adding new ' + task.name)
    stat = ical_event_add(task)
  # Last resort
  if not stat:
    error('Update of caldav last resort, forced remove add, of ' + task.name)
    if not universe.dry:
      stat_remove = ical_event_delete(task, name=name)
      if not stat_remove:
        stat_remove = ical_event_delete(task)
      stat_add = ical_event_add(task)
      stat = stat_remove and stat_add
    else:
      stat = True
  return stat

def task_create(task=None, title='Task title', due=None, alarm=None, note='', sequence=0, uid=None, priority=None, next_action=None):
  from uuid import uuid4
  from icalendar import Calendar, Todo, Alarm
  if task is not None:
    title = task.name
    due = task.due
    alarm = task.alarm
    note = task.note
    sequence = task.sequence
    priority = task.priority
    next_action = task.next_action
  if (due is not None and alarm is None):
    # Should not arrive here, this should have already have been handled
    alarm = due
    if is_same_time(due, universe.defaulttime.due):
      # Warning for day events 1800 - 1000 = 8 hours
      alarm = due + universe.defaulttime.alldaydiff
    else: 
      # Default warning of an hour
      alarm = due + universe.defaulttime.diff
  if (alarm is not None and due is None):
    due = alarm
  # alarm now defunct - just use due
  cal = Calendar()
  cal.add('prodid', '-//enoky//v0.1//EN')
  cal.add('version', '2.0')

  todo = Todo()
  todo.add('summary', title)
  if priority is not None:
    todo.add('priority', priority)
  if due is not None:
    todo.add('due', due)
    todo.add('dtstart', due)
  todo.add('status', 'NEEDS-ACTION')
  todo.add('dtstamp', universe.now)
  todo.add('created', universe.now)
  if uid is None:
    uid = uuid4()
  todo['uid'] = uid
  todo.add('sequence', sequence)
  notenext = note
  if (next_action is not None) and (len(next_action) > 0):
    if len(notenext) > 0:
      notenext = notenext + '\n'
    notenext = notenext + universe.next_char + ' ' + next_action.lstrip()
  if len(notenext) > 0:
    todo.add('description', notenext)

  if alarm is not None:
    valarm = Alarm()
    valarm['uid'] = uuid4()
    valarm.add('trigger', alarm)
    # Possibly not needed. How add due date?!
    valarm.add('description', 'Event reminder')
    valarm.add('action', 'DISPLAY')
    todo.add_component(valarm)

  cal.add_component(todo)
  vcal = cal.to_ical()
  return vcal

def task_add(client, calendar, task):
  from caldav import Event
  # Add option to supply a 'task' like task_create
  vcal = task_create(task=task)
  try:
    if not universe.dry:
      #print vcal
      event = Event(client, data = vcal, parent = calendar).save()
  except Exception, e:
    if universe.debug: raise
    error('Task add problem ' + str(e))
    event = None
    pass
  return event

def ical_parse_date(string):
  # Could limit use of try and check when type of object string is (i.e. datetime, date, ...)
  if string is None:
    return None
  #print '---- ', string.params
  try:
    date = string.dt
    #print '    dt', string, '->', date
  except Exception, e:
    error('Date parse error [' + str(string) + ']' + ' Exception: ' + str(e))
    return None

  # Add timezone information
  # Assume local if no timezone info
  try:
    if 'TZID' in string.params.keys():
      import pytz
      tz = pytz.timezone(string.params['TZID'])
    else:
      tz = universe.timezone
  except:
    tz = universe.timezone
    pass
    
  temp = None
  try:
    temp = tz.localize(date)
  except Exception, e:
    pass
  if temp is not None:
    #print '    lo', date, '->', temp
    date = temp

  # Shift values around so in local system
  temp = None
  try:
    temp = date.astimezone(universe.timezone)
  except Exception, e:
    pass
  if temp is not None:
    #temp = temp.replace(tzinfo=None)
    #temp = universe.timezone.localize(temp)
    #print '    as', date, '->', temp
    date = temp
  return date


