#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from Parsers import prioritystring, spacedemoji

class Events(object):
  def __init__(self, events = None, name='event group not named'):
    if events is None: events = []
    self.name = name
    self.events = events
    self.names = self.find_names()
    self.next_action = ''
    if name == 'caldav':
      self.calendartype = 'caldav'
    elif name == 'active':
      self.calendartype = 'active'
    else:
      self.calendartype = 'custom'
      
  def is_caldav(self):
    if self.calendartype == 'caldav':
      return True
    return False

  def is_file(self):
    if self.calendartype == 'active':
      return True
    return False

  def is_real(self):
    return (self.is_file() or self.is_caldav())

  def find_names(self):
    names = []
    for event in self.events:
      names.append(event.name)
    return names

  def find_tasks_by_name(self, name, check_is_wait=False):
    events = []
    for event in self.events:
      if ( ((not check_is_wait) and event.name == name) or ((not check_is_wait) and event.name == name) ):
        events.append(event)
    return events

  def find_task(self, task):
    for event in self.events:
      if event.is_same_task(task):
        return event
    return None

  def contains_task_by_name_group(self, name, group):
    found = False
    for event in self.events:
      #print 'name:   ', name, '|', event.name
      #print 'parent: ', parent, '|', event.parents[0]
      if (event.name == name and event.group() == group):
        found = True
        break
    return found

  def contains_task_by_name_parent(self, name, parent):
    found = False
    for event in self.events:
      if (event.name == name and event.parents[0] == parent):
        found = True
        break
    return found

  def find_all_task_occurances(self, task, occurances=None):
    if occurances == None:
      occurances = 0
    cache = []
    for t in self.events:
      if t.is_same_task(task):
        occurances +=1
        cache.append(t)
    if occurances > 1:
      report(colour.grey + (('  DUPLICATE CALDAV: %i' % occurances) + os.linesep + os.linesep.join(['    ' + x.name + ' ' + x.group() for x in cache ])) + colour.end)
    return occurances

  def task_is_present(self, task):
    found = False
    for event in self.events:
      #if event.name == name:
      if event.is_same_task(task):
        found = True
    return found

  def find_number(self):
    return len(self.events)

  def extend(self, events):
    # Note doesn't alter caldav like add
    self.events.extend(events)
    self.names = self.find_names()

  def add(self, event):
    if not self.task_is_present(event):
      if self.is_real():
        report(colour.green + 'Adding task to' + colour.end + ' ' + colour.greenbright + self.calendartype + colour.green + ' in ' +  event.parents[0] + colour.green + ':' + colour.end + ' ' + event.name)
        if not universe.dry:
          if self.is_caldav():
            from CaldavClient import ical_event_add
            ical_event_add(event)
      self.events.append(event)
      self.names = self.find_names()

  def remove(self, event):
    new = []
    for e in self.events:
      #if (e.name == event.name and e.group() == event.group()):
      if e.is_same_task(event):
        if self.is_real():
          report(colour.red + 'Removing task from' + colour.end + ' ' + colour.redbright + self.calendartype + '|' + e.parents[0] + colour.red + ':' + colour.end + ' ' + e.name)
          if not universe.dry:
            if self.is_caldav():
              from CaldavClient import ical_event_delete
              ical_event_delete(e)
            # remove from file? - just leave to end?  
      else:
        new.append(e)
    self.events = new
    self.names = self.find_names()

  def remove_all(self):
    for event in self.events:
      self.remove(event)

  def to_string(self, show_next_action=True, raw=False):
    iro = generate_mono(raw)
    events = ''
    for event in self.events:
      if event.note is None:
        note = ''
      elif len(event.note) == 0:
        note = ''
      else:
        note = os.linesep + os.linesep.join([ ' ' * 4 + notelines for notelines in event.note.splitlines() ])
        note = iro.grey + note + iro.end

      if show_next_action and (self.next_action is not None) and (len(str(self.next_action)) > 0):
        next_action = ' ' + iro.green + universe.next_char + str(self.next_action) + iro.end
      else:
        next_action = ''

      out_priority = prioritystring(event.priority, spacer=True)

      eventtext = '''\
%(name)s%(parents)s%(due)s%(alarm)s%(priority)s%(sequence)s%(group)s%(next)s%(note)s''' \
      % {
        'name': event.name, 
        'parents': ' ' + iro.grey + '' + iro.end + iro.magenta + ':'.join(event.parents) + iro.grey + '' + iro.end if len(event.parents) > 0 else '',
        'due': '' if event.due is None else ' ' + iro.cyan + event.due.strftime('%y%m%d%H%M') + iro.end,
        'alarm': '' if event.alarm is None else ' ' + iro.red + event.alarm.strftime('%y%m%d%H%M') + iro.end,
        'priority': iro.redbright + out_priority + iro.end,
        'group': iro.blue + ' ' + str(event.group()) + iro.end,
        'note': note, 
        'sequence': (iro.blue + ' %i' + iro.end) % event.sequence,
        'next': next_action,
      }

      events = events + os.linesep + '  ' + eventtext
    text = '''\
%(name)s %(number)s%(events)s''' \
      % {
        'name': self.name,
        'number': iro.yellow + str(self.find_number()) + iro.end,
        'names': iro.blue + (os.linesep + '  ').join([''] + self.names) + iro.end,
        'events': events, 
      }
    return text
  
  def __str__(self):
    return self.to_string()

  def show(self, show_notes=True, wait_separate=False, priority_only=False, inbox_only=False, show_empty=False):
    categories = dict()
    for task in self.events:
      parent = task.parents[0]
      if parent not in categories.keys():
        categories[parent] = []
      categories[parent].append(task)

    category_order = universe.category_order

    show_next_action = True

    complete = []
    wait_list = []
    #empty = 'empty'
    empty = '無'.decode('utf-8')
    for category in category_order + categories.keys():
      if category not in categories.keys(): continue
      if category in complete: continue
      out = []
      complete.append(category)
      out.append(colour.blue + category.upper() + colour.end)
     
      number = 0
      tasks = sorted(categories[category])
      for task in tasks:
        if inbox_only and task.parents[-1] != 'inbox':
          continue
        if priority_only and (not task.is_overdue_today_tomorrow_important()):
          continue
        if wait_separate and task.is_wait():
          wait_list.append(task)
          continue
        out.append(task.to_string(indentnone=True, notes=show_notes, show_where=True, show_next_action=show_next_action, show_translate_inheritance=True))
        number += 1
      if (number == 0) and show_empty:
        out.append(colour.grey + '  ' + empty + colour.end)
      if len(out) > 1:
        out = '\n'.join(out)
        out = spacedemoji(out)
        report(out, forced=True)

    # WAIT tasks
    out = []
    if wait_separate:
      number = 0
      out.append(colour.blue + 'wait'.upper() + colour.end)
      for task in wait_list:
        out.append(task.to_string(indentnone=True, notes=show_notes, show_where=True, show_next_action=show_next_action, show_translate_inheritance=True))
        number += 1
      if (number == 0) and show_empty:
        out.append(colour.grey + '  ' + empty + colour.end)
      if len(out) > 1:
        out = '\n'.join(out)
        out = spacedemoji(out)
        report(out, forced=True)
        #report('\n'.join(out), forced=True)
    




