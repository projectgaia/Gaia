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
from datetime import datetime, timedelta, date, time
import icalendar

from Support import error, report
from Support import generate_mono
from Parsers import prioritystring, is_same_time, timedelta_to_human
from FileTodo import FileTodos 
from CaldavClient import ical_parse_date
from CaldavClient import ical_event_update, ical_event_add, ical_event_delete

class CalTodo(object):
  def __init__(self, event, calendarname=''):
    self.name = None
    self.parents = [ calendarname ]
    self.groupname = calendarname
    self.status = None
    self.duetext = None
    self.completed = None
    self.due = None
    self.sequence = 0
    self.note = ''
    self.uid = ''
    self.alarmtext = None
    self.alarm = None
    self.priority = None
    self.wait = ''
    self.titleoptions = ''
    self.next_action = None
    self.repeat = None
    if str(event).endswith('/'):
      return
    self.read(event)
    self.type='caldav'

  def parsedata(self, event):
    # Contains SSLContext object, which can't be pickled
    # eventdata = event.get_data()
    # This below failed once, second run passed so just a random error
    try:
      event.load()
      data = icalendar.Calendar().from_ical(event.get_data())
      return data
    except:
      pass
    return None

  def read(self, event):
    if self.groupname == 'wait':
      self.wait = 'wait'
    data = self.parsedata(event)
    if data is None:
      data = self.parsedata(event)
      if data is None:
        self.readstat = False
        return
    for component in data.walk():
      if component.name == "VTODO":
        try:
          self.name = component.get('summary')
        except: pass
        try:
          self.status = component.get('status')
        except: pass
        try:
          self.uid = component.get('uid')
        except: pass
        try:
          self.completed = component.get('completed')
        except: pass
        try:
          self.duetext = component.get('due')
        except: pass
        try:
          self.sequence = component.get('sequence')
        except: pass
        try:
          self.priority = component.get('priority')
        except: pass
        try:
          self.note = component.get('description')
          if self.note is None:
            self.note = ''
        except: pass
      elif component.name == "VALARM":
        # Use last alarm time
        try:
          alarmtext = component.get('trigger')
          if alarmtext is not None:
            self.alarmtext = component.get('trigger')
        except: pass
    
    modified_times = False
    self.due = ical_parse_date(self.duetext)
    self.alarm = ical_parse_date(self.alarmtext)

    if type(self.due) is date:
      self.due = universe.timezone.localize(datetime(year=self.due.year, month=self.due.month, day=self.due.day, hour=universe.defaulttime.due.hour, minute=universe.defaulttime.due.minute))
      modified_times = True

    if self.completed is not None:
      self.status = 'COMPLETED'
    #Allow due = alarm, not tested:
    #if (self.due is not None and ( self.alarm is None or ( self.alarm == self.due and not 'instantaeousalarm' in self.notes) ) ):
    if (self.due is not None and ( self.alarm is None or self.alarm == self.due ) ):
      if is_same_time(self.due, universe.defaulttime.due):
        # Warning for day events 1800 - 1000 = 8 hours
        self.alarm = self.due + universe.defaulttime.alldaydiff
      elif is_same_time(self.due, universe.defaulttime.duealt):
        self.due = self.due - universe.defaulttime.duealtdelta + universe.defaulttime.duedelta
        self.alarm = self.due + universe.defaulttime.alldaydiff
      else: 
        # Default warning of an hour
        self.alarm = self.due + universe.defaulttime.diff
      modified_times = True
    # Shouldn't get here!
    elif (self.alarm is not None and self.due is None):
      if is_same_time(self.alarm, universe.defaulttime.due):
        # Warning for day events 1800 - 1000 = 8 hours
        self.due = self.alarm
        self.alarm = self.due + universe.defaulttime.alldaydiff
      else: 
        # Default warning of an hour
        self.due = self.alarm
        self.alarm = self.due + universe.defaulttime.diff
      modified_times = True

    modified_options = False
    if '  ' in self.name:
      # Ensure options that appear in the title are post-pended
      self.name, self.titleoptions = self.name.split('  ', 1)
      self.name = self.name.strip()
      self.titleoptions = self.titleoptions.strip()
      modified_options = True

    if modified_times or modified_options:
      detail = ''
      if modified_times:
        detail = detail + ' due: %(due)s, alarm: %(alarm)s' % {
          'due': '[empty]' if self.due is None else self.due.strftime('%y%m%d%H%M'),
          'alarm': '[empty]' if self.alarm is None else self.alarm.strftime('%y%m%d%H%M'),
        }
      if modified_options:
        detail = detail + ' parsed options: ' + self.titleoptions

      report(colour.yellow + 'Updating task import times and options in' + colour.end + ' ' + colour.yellowbright + 'caldav' + '|' + self.parents[0] + colour.yellow + ':' + colour.end + ' ' + self.name + colour.grey + detail + colour.end)
      ical_event_update(self, due=True)

    self.readstat = True
    notelines = []
    for line in self.note.splitlines():
      if line.startswith(universe.next_char + ' '):
        self.next_action = line[2:]
        #print '****   ', self.next_action
        continue
      notelines.append(line)
    self.note = '\r'.join(notelines)

  def is_same_task(self, task):
    if (len(self.parents) == 0 or len(task.parents) == 0):
      return self.name == task.name
    else:
      return (self.name == task.name and self.parents[0] == task.parents[0])

  def is_wait(self):
    if self.wait is not None:
      if len(self.wait) > 0:
        return True
    return False

  def set_wait(self, string=None):
    if string is None:
      string = 'wait'
    self.wait = string

  def group(self):
    #group = self.parents[0]
    return self.groupname

  def update(self, task, due=False, note=False, priority=False, wait=False):
    error("Shouldn't find yourself here no more! In CalTodo.update.")
    detail = ''
    if priority:
      detail = detail + ' priority: %(old)s -> %(new)s' % {
        'old': prioritystring(self.priority, shownone=True),
        'new': prioritystring(task.priority, shownone=True),
      }
      self.priority = task.priority
    if due:
      detail = detail + ' due: %(old)s -> %(new)s, alarm: %(aold)s -> %(anew)s' % {
        'old': '[empty]' if self.due is None else self.due.strftime('%y%m%d%H%M'),
        'new': '[empty]' if task.due is None else task.due.strftime('%y%m%d%H%M'),
        'aold': '[empty]' if self.alarm is None else self.alarm.strftime('%y%m%d%H%M'),
        'anew': '[empty]' if task.alarm is None else task.alarm.strftime('%y%m%d%H%M'),
      }
      self.due = task.due
      self.alarm = task.alarm
    if wait:
      detail = detail + ' wait: %(old)s -> %(new)s' % {
        'old': '[empty:'+str(self.wait)+']' if (self.wait is None or self.wait == '') else self.wait,
        'new': '[empty:'+str(task.wait)+']' if (task.wait is None or task.wait == '') else task.wait
      }
      self.wait = task.wait
    if note:
      detail = detail + ' note: %(old)s -> %(new)s' % {
        'old': '[empty:'+str(self.note)+']' if (self.note is None or self.note == '') else ' + '.join(self.note.splitlines()),
        'new': '[empty:'+str(task.note)+']' if (task.note is None or task.note == '') else ' + '.join(task.note.splitlines()),
      }
      self.note = task.note
    #self.sequence_increment()
    report(colour.yellow + 'Updating task in' + colour.end + ' ' + colour.yellowbright + 'caldav' + '|' + self.parents[0] + colour.yellow + ':' + colour.end + ' ' + self.name + colour.grey + detail + colour.end)
    ical_event_update(self, due=due, note=note, priority=priority)

  def sequence_increment(self):
    self.sequence += 1 

  def is_valid(self):
    return self.name is not None

  def is_complete(self):
    return self.status == 'COMPLETED'

  def allday(self):
    return (is_same_time(self.due, universe.defaulttime.due) and is_same_time(self.alarm, universe.defaulttime.alarm) )

  def to_string(self, reformat=False, raw=True):
    iro = generate_mono(raw or reformat)
    if not self.is_valid():
      return iro.red + 'Not a valid event' + iro.end

    if self.note is None:
      note = ''
    elif len(self.note) == 0:
      note = ''
    else:
      note = os.linesep + os.linesep.join([ ' ' * 4 + notelines for notelines in self.note.splitlines() ])
      if not (raw or reformat):
        note = iro.grey + note + iro.end

    out_due = ''
    out_due_date = None
    if self.due is not None:
      out_due_date = self.due
    elif self.alarm is not None:
      out_due_date = self.alarm
    else:
      out_due = ''
     
    if out_due_date is not None:
      if self.allday():
        out_due = out_due_date.strftime('%y%m%d')
      else:
        out_due = out_due_date.strftime('%y%m%d%H%M')

    # Work out diff
    if self.alarm is not None:
      out_alarm = self.alarm.strftime('%y%m%d%H%M')
      if self.due is not None:
        d = self.alarm - self.due
        if (self.allday() and d == universe.defaulttime.alldaydiff):
          out_alarm = ''
        elif (not self.allday() and d == universe.defaulttime.diff):
          out_alarm = ''
        else:
          dh = timedelta_to_human(d)
          if dh is not None:
            out_alarm = dh
    else:
      out_alarm = ''
    if len(out_alarm) > 0:
      out_alarm = ' !' + out_alarm
    if len(out_due) > 0:
      out_due = ' ' + out_due

    out_priority = prioritystring(self.priority, spacer=True)

    if (self.group() == self.parents[0] or self.group() == 'wait' ):
      translate = ''
    else:
      translate = ' =' + self.group()
 
    if len(self.titleoptions) > 0:
      titleoptions = ' ' + self.titleoptions
    else:
      titleoptions = ''

    if reformat:
      options = '''\
%(due)s%(alarm)s%(translate)s%(wait)s%(priority)s%(titleoptions)s''' \
        % {
          'due': out_due,
          'alarm': out_alarm,
          'priority': out_priority,
          'translate': translate,
          'wait': ' wait' if self.group() == 'wait' else '',
          'titleoptions': titleoptions,
        }

      spacer = ''
      endspacer = ''
      if (len(options) > 0 and '  ' not in self.name):
        spacer = ' '
      if (len(options) == 0 and '  ' not in self.name):
        endspacer = '  '
        
      text = '''%(name)s%(spacer)s%(options)s%(endspacer)s%(note)s''' \
        % {
          'name': self.name,
          'spacer': spacer,
          'options': options,
          'note':note,
          'endspacer': endspacer,
        }
    else:
      text = '''\
  %(name)s%(due)s%(priority)s%(note)s''' \
        % {
          'name':self.name,
          'duetext': '' if self.duetext is None else ' ' + str(self.duetext),
          'due': '' if self.due is None else ' ' + self.due.strftime('%y%m%d%H%M'),
          'priority': iro.redbright + out_priority + iro.end,
          'status': '' if self.status is None else ' ' + self.status,
          'sequence': ' ' + iro.grey + '(' + iro.cyan + str(self.sequence) + iro.grey + ')' + iro.end,
          'note':note,
        }
      text = os.linesep.join([ notelines for notelines in text.splitlines() ])
    return text

  def reformat(self):
    return self.to_string(reformat=True) + os.linesep

  def __str__(self):
    return self.to_string()



