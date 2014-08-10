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
from datetime import datetime, timedelta
import re
from uuid import uuid4

from Support import error, report
from Support import generate_mono
from Support import repo_add, repo_remove, repo_update
from Parsers import is_relative_date, calculate_delta, prioritystring, is_same_time, timedelta_to_human, do_avoid_weekend, next_weekday, next_increment

def indentation(s, tabsize=2):
  sx = s.expandtabs(tabsize)
  return (len(sx) - len(sx.lstrip()))/tabsize
  #return 0 if sx.isspace() else (len(sx) - len(sx.lstrip()))/tabsize

def parsedate(string, reference=None, alarm=False, allday=False, forward=False):
  date = None
  if (string is None or len(string) == 0):
    if alarm:
      if reference is not None:
        if allday:
          # Warning for day events 1800 - 1000 = 8 hours
          date = reference + universe.defaulttime.alldaydiff
        else:
          # Default warning of an hour
          date = reference + universe.defaulttime.diff
  else:
    string = string.strip()
    # Deal with tasks due on a day, not specific time
    if len(string) == 6:
      allday = True
      if alarm:
        string = string + universe.defaulttime.alarm.strftime('%H%M')
      else:
        string = string + universe.defaulttime.due.strftime('%H%M')
    try:
      if re.match('^\d{6}$', string):
        date = datetime.strptime(string, '%y%m%d') 
      elif re.match('^\d{10}$', string):
        try:
          date = universe.timezone.localize(datetime.strptime(string, '%y%m%d%H%M'))
          #date = datetime.strptime(string, '%y%m%d%H%M')
        except Exception, e:
          date = None
          error('Date parse error [' + string + ']' + ' Exception: ' + str(e))
          if universe.debug: raise
          pass
      elif is_relative_date(string):
        d = calculate_delta(string)
        if d is not None:
          if reference is not None:
            if forward:      
              date = reference + d
            else:
              date = reference - d
      else:
        date = universe.timezone.localize(datetime.strptime(string))
        #date = datetime.strptime(string)
    except Exception, e:
      date = None
      error('Date parse error [' + string + ']' + ' Exception: ' + str(e))
      if universe.debug: raise
      pass
  return date, allday

def tasklist_read(name, category=None):
  if category is None:
    filename = universe.dataroot + name
  else:
    filename = universe.dataroot + category + '/' + name
  if not os.path.exists(filename):
    return None
  f = open(filename, 'r')
  level = 0
  taskline = ''
  notes = ''
  lines = (f.read().decode('utf8') + os.linesep).splitlines()
  f.close()
  #end = len(lines)
  #blank = False
  #for i in range(len(lines)):
  #  if len(lines[i]) > 0:
  #    blank = False
  #    continue
  #  if not blank:
  #    blank = True
  #    continue
  #  end = i
  #  break

  # Temp
  #end = len(lines)
  #root = FileTodos(lines[:end], title=name, parents=[category], filenotes=lines[end+1:])
  
  root = FileTodos(lines, title=name, parents=[category])
  root.check_for_modified_children() 

  if root.is_empty():
    report('  ' + colour.grey + 'Removing EMPTY ' + colour.blue + category + colour.grey + '/' + colour.yellowbright + root.name + colour.end + ' ' + colour.grey + '(' + colour.grey + filename + colour.grey + ')' + colour.end)
    if not universe.dry:
      root.set_modified()
      try:
        if os.path.exists(filename):
          os.remove(filename)
          repo_remove(filename)
      except:
        pass

  return root


class FileTodos(object):
  def __init__(self, lines=None, filenotes=None, parents=[], parent=None, title=None, flow='parallel', translate=None, number=1, level=None, uid=None, caldav=False, next_action=None):
    self.lines = None
    self.filenotes = filenotes
    if self.filenotes is None:
      self.filenotes = []
    self.block = []
    self.level = -2
    # top level modified flag for file updates
    self.modified = False
    # task level update flag for caldav
    self.updated = False
    self.sequence = 0
    if lines is not None:
      self.lines = lines
      self.block = [ 0, len(self.lines) ]
      if title is not None:
        self.level = 0
      else:
        self.level = indentation(self.lines[0]) + 1
        title = self.lines[0].lstrip()
    if level is not None:
      self.level = level
    self.name = None
    self.duetext = None
    self.alarmtext = None
    self.is_checklist = False
    self.flowtext = None
    self.flow = flow
    self.is_header = False
    self.is_completed = False
    #if caldav: 
    #  self.is_onhold = None
    #  self.starttext = None
    #  self.repeat = None
    #else:
    #self.is_everpresent = False
    self.is_onhold = False
    self.starttext = None
    self.repeat = None
    self.expiretext = None

    self.wait = ''
    self.waitonrepeat = False
    self.priority = None
    self.is_permanent = False
    self.avoidweekends = False
    self.current = False
    self.error = False
    self.sublist = None
    self.parents = parents
    self.parent = parent
    self.number = number
    self.uid = uid
    self.translate = ''
    if translate is not None:
      self.translate = translate
    self.interpret_task(title)
    #if len(self.translate) > 0:
    #  print self.name, self.translate
    
    self.note = self.find_note()
    self.childblocks = self.identify_blocks()
    self.children = []
    self.due, allday = parsedate(self.duetext)
    self.alarm, allday = parsedate(self.alarmtext, reference=self.due, alarm=True, allday=allday)

    self.start, allday = parsedate(self.starttext, reference=self.due)
    self.expire, allday = parsedate(self.expiretext, reference=self.due, forward=True)
    self.active = False
    self.titleoptions = ''
    self.type = 'file'
    self.next_action = next_action
    if self.next_action is not None:
      self.next_action = next_action.lstrip()

    # Need to add next action, in case of checklist, main header is first??
    
    if lines is not None:
      if len(self.childblocks) > 0:
        filenotesstart = self.childblocks[-1][-1]
      else:
        filenotesstart = 0

      i = filenotesstart
      for i in range(filenotesstart, len(lines)):
        if len(lines[i]) > 0:
          filenotesstart = i
          break

      if self.level == 0:
        #print self.name, filenotesstart
        if filenotesstart < len(lines):
          if lines[filenotesstart] is not None:
            if len(lines[filenotesstart]) > 0:
              self.filenotes = lines[filenotesstart:]

    if len(self.childblocks) > 0:
      self.find_children()

  def child_is_task(self, task):
    found = False
    for child in self.children:
      if child.is_same_task(task):
        found = True
        break
    return found

  def is_empty(self):
    return (not self.has_children() and len(self.filenotes) == 0)

  def is_same_task(self, task):
    if (len(self.parents) == 0 or len(task.parents) == 0):
      return self.name == task.name
    else:
      return (self.name == task.name and self.parents[0] == task.parents[0])

  def is_translate_header(self):
    if self.has_children():
      if self.is_translate():
        if self.parent is None:
          return True
        else:
          if not self.parent.is_translate():
            return True
    return False

  def group(self, masked=True):
    if self.is_wait() and masked:
      group = 'wait'
    elif (self.is_translate() and (not self.is_translate_header()) and masked):
      group = self.translate
    elif len(self.parents) > 0:
      group = self.parents[0]
    else:
      # Either root of tree, or an un-tied task!
      group = 'home'
    return group

  def allday(self):
    return (is_same_time(self.due, universe.defaulttime.due) and is_same_time(self.alarm, universe.defaulttime.alarm) )

  def do_repeat(self):
    avoid_weekends = (self.group(masked=False) in universe.skipweekendlists or self.avoidweekends)
    # Deal with permanent task
    if self.is_permanent:
      #self.is_onhold = True
      detail = ''
      if self.waitonrepeat:
        self.wait = 'wait'
        detail = ' and moved to wait status'
      self.set_updated()
      report(colour.yellow + 'Permenant task' + detail + colour.end + ' ' + colour.yellowbright + '|'.join(self.parents) + colour.yellow + ':' + colour.end + ' ' + self.name + colour.end)
      return
    if (self.repeat is None or len(self.repeat) == 0): return
    if (self.due is None): return
    d = None
    if self.waitonrepeat:
      self.wait = 'wait'
    self.set_updated()
    every = False
    after = False
    random = False
    string = self.repeat
    if string in ['decennially', 'biennially', 'annually', 'monthly', 'fortnightly', 'weekly', 'daily']:
      every = True
      if string == 'decennially':
        string = '10years'
      elif string == 'biennially':
        string = '2years'
      elif string == 'annually':
        string = 'year'
      elif string == 'monthly':
        string = 'month'
      elif string == 'fortnightly':
        string = '2weeks'
      elif string == 'weekly':
        string = 'week'
      elif string == 'daily':
        string = 'day'
    elif re.match('^every\w+$', string):
      every = True
      string = string[5:]
    elif re.match('^after\w+$', string):
      after = True
      string = string[5:]
    elif re.match('^random$', string):
      random = True
    if every or after or random:
      d = calculate_delta(string)
    if d is not None:
      # Including case of absolute date
      new_due = None
      new_start = None
      new_alarm = None
      detail = ''

      if every:
        # Ensure at least advanced by one d delta
        multi = 1
        while (self.due + d * multi) < universe.now:
          multi += 1
          if multi > 1000:
            multi = 1
            error('Determining multiple every recur time delta for (>1000) ' + self.name)
            break
        #print 'A', d * multi
        #print 'B', self.due
        #print 'C', self.due + d * multi
        #multi = 0
        #d = d * multi
        #dmulti = int((universe.now - self.due).total_seconds() // d.total_seconds())
        #if dmulti > 0:
        #  # Event very overdue, such that subsequent repeats missed
        #  d = (dmulti + 1) * d
        #  #print "Multi d event", d, dmulti
        new_due = self.due + d * multi
        if self.start is not None:
          if is_relative_date(self.starttext):
            new_start = self.start + d * multi
            
      elif (after or random):
        if after:
          # Use .replace on datetime object instead? 
          #shift = ((self.due.hour - universe.now.hour) * 60 + (self.due.minute - universe.now.minute)) * 60 + self.due.second - universe.now.second
          #new_due = universe.now + d + timedelta(seconds=shift) + timedelta(microseconds=-universe.now.microsecond) 
          #
          new_due = universe.now.replace(second=0, microsecond=0)
          shift = (self.due.hour - new_due.hour) * 60 + self.due.minute - new_due.minute
          new_due = new_due + d + timedelta(minutes=shift)
          #
        elif random:
          new_due = universe.now.replace(second=0, microsecond=0) + d
          new_due = do_avoid_weekend(new_due, avoid_weekends=avoid_weekends)

        if (self.starttext is not None and len(self.starttext) > 0):
          string = self.starttext
          if is_relative_date(string):
            d = calculate_delta(string)
            if d is not None:
              new_start = new_due - d

      if self.alarm is not None:
        if self.alarmtext is not None:
          self.alarm, allday = parsedate(self.alarmtext, reference=new_due, alarm=True, allday=self.allday())
        elif self.allday():
          # Warning for day events 1800 - 1000 = 8 hours
          new_alarm = new_due + universe.defaulttime.alldaydiff
        else: 
          # Default warning of an hour
          new_alarm = new_due + universe.defaulttime.diff
      if new_due is not None:
        detail = detail + ' due: %(old)s -> %(new)s' % {
          'old': '[empty]' if self.due is None else self.due.strftime('%y%m%d%H%M%z'),
          'new': '[empty]' if new_due is None else new_due.strftime('%y%m%d%H%M%z')
        }
        self.due = new_due
      if new_start is not None:
        detail = detail + ' start: %(old)s -> %(new)s' % {
          'old': '[empty]' if self.start is None else self.start.strftime('%y%m%d%H%M%z'),
          'new': '[empty]' if new_start is None else new_start.strftime('%y%m%d%H%M%z')
        }
        self.start = new_start
      if new_alarm is not None:
        detail = detail + ' alarm: %(old)s -> %(new)s' % {
          'old': '[empty]' if self.alarm is None else self.alarm.strftime('%y%m%d%H%M%z'),
          'new': '[empty]' if new_alarm is None else new_alarm.strftime('%y%m%d%H%M%z')
        }
        self.alarm = new_alarm
      report(colour.yellow + 'Recur task in' + colour.end + ' ' + colour.yellowbright + '|'.join(self.parents) + colour.yellow + ':' + colour.end + ' ' + self.name + colour.grey + detail + colour.end)
    else:
      error('Determining recur time delta for ' + self.name + ' string[' + string + ']')
    return

  def add(self, task):
    if len(task.parents) == 1:
      lists = []
      for c in self.children:
        if c.name == task.parents[0]:
          lists = c.child_names()
          break
      if (task.sublist is None) or not (task.sublist in lists):
        if (task.sublist is not None) and not (task.sublist in lists):
          report(colour.red + 'Selected sublist ' + task.sublist + ' not present, adding to the inbox' + colour.end)
        task.sublist = 'inbox'
      task.parents.append(task.sublist)
      task.sublist = None
    match = self
    for group in task.parents:
      found = False
      for child in match.children:
        if child.name == group:
          found = True
          match = child
          break
    if not found:
      inbox = FileTodos(title='inbox', parents=match.parents + [match.name], parent=match, translate=self.translate, level=match.level + 1)
      match.add_child(inbox)
      match = inbox
      found = True
   
    match.set_modified(task)

    new = FileTodos(lines=task.reformat().splitlines(), parents=match.parents + [match.name], parent=match)
    report(colour.green + 'Adding task to ' + colour.greenbright + 'file' + colour.green + ' in ' +  '|'.join(new.parents) + colour.green + ':' + colour.end + ' ' + new.name)
    match.add_child(new)

  def find_task(self, task):
    match = None
    if self.is_same_task(task):
      return self
    for child in self.children:
      match = child.find_task(task)
      if match is not None:
        match = match.find_task(task)
        break
    return match

  def find_tasks_by_name(self, task=None, name=None, matches=None, check_is_wait=False):
    if matches is None:
      matches = []
    if task is not None:
      name = task.name
    if name == self.name:
      if (not check_is_wait or (check_is_wait and self.is_wait()) ):
        matches.append(self)
    for child in self.children:
      matches = child.find_tasks_by_name(name=name, matches=matches)
    return matches

  def find_task_parent(self, task):
    #if task.name in self.child_names():
    if self.child_is_task(task):
      return self
    for child in self.children:
      parents = child.find_task_parent(task)
      if parents is not None:
        return parents
    return None

  def children_all_completed(self):
    allcomplete = True
    for child in self.children:
      if not child.is_completed:
        allcomplete = False
    return allcomplete

  def uncomplete_childen(self):
    self.is_completed = False
    for child in self.children:
      child.uncomplete_childen()

  def unwait_childen(self):
    # Assumes working just after uncompleted (for waitonrepeat test)
    if self.waitonrepeat:
      self.wait = 'wait'
    else:
      self.wait = ''
    for child in self.children:
      child.unwait_childen()

  def is_repeat(self):
    if self.repeat is not None:
      if len(self.repeat) > 0:
        if self.due is not None:
          return True
    if self.is_permanent:
      return True
    return False

  def recur(self, task, root=None, recursive=False):
    if root is None:
      root = self
    match = None
    removed = False
    #if task.name in self.child_names():
    if self.child_is_task(task):
      for child in self.children:
        #if child.name == task.name:
        if child.is_same_task(task):
          match = child
          break
      # Should complete/remove any children here - otherwise need to wait for next run 
      match.uncomplete_childen()
      match.unwait_childen()
      if ((match.repeat is not None and match.due is not None) or match.is_permanent):
        match.do_repeat()
        #match.update()
      else:
        root.remove(task)
        removed = True
    else:
      for child in self.children:
        match = child.recur(task, root=root, recursive=True)
        if match is not None:
          break
    if not recursive:
      if match is not None:
        self.make_modified(match)
    if removed: return None
    return match


  def remove(self, task, root=None, repeats=False, recursive=False):
    if root is None:
      root = self
    match = None
    if self.child_is_task(task):

      # Check if new tasks become active
      if self.is_repeat():
        repeats = True
      new_children = []
      for child in self.children:
        #if child.name == task.name:
        if child.is_same_task(task):
          match = child
          if repeats:
            match.is_completed = True
        else:
          new_children.append(child)
      if not match.is_header:
        if repeats:
          action = 'Completing'
        else:
          self.children = new_children
          action = 'Removing'
        stat = colour.greenbright + 'OK' + colour.end if match is not None else colour.redbright + 'FAIL' + colour.end
        report(colour.red + action + ' task from full tree in' + colour.end + ' ' + colour.redbright + 'file' + '|' + '|'.join(match.parents) + colour.red + ':' + colour.end + ' ' + match.name + ' ' + stat)
    else:
      if self.is_repeat():
        repeats = True
      for child in self.children:
        match = child.remove(task, root=root, repeats=repeats, recursive=True)
        if match is not None:
          break
      # Check if parent requires removal
      if match is not None:
        # removed: child, parent: self  X actually match?
        if child.level > 0:
          if child.name == match.parents[-1]:
            if (child.is_repeat() or repeats):
              if child.children_all_completed():
                report(colour.red + '  need to complete parent also, ' + colour.redbright + child.name + colour.end)
                # Uncomplete all children of child
                child.uncomplete_childen()
                child.unwait_childen()
                if child.is_repeat():
                  # Apply repeat to child
                  child.do_repeat()
                else:
                  self.remove(child, repeats=repeats, recursive=True)
                  match = child
            else:
              if not child.has_children():
                if not child.is_header:
                  report(colour.red + '  need to remove parent also, ' + colour.redbright + child.name + colour.end)
                  self.remove(child, recursive=True)
                  match = child
    if not recursive:
      if match is not None:
        self.make_modified(match)
    return match

  def clear_titleoptions(self):
    self.starttext = None
    self.repeat = None
    #self.is_onhold = False

  def is_equal(self, other, caldav=False):
    if (self.due != other.due):
      return False
    if (self.alarm != other.alarm):
      return False 
    if (self.note != other.note):
      return False
    if (self.priority != other.priority):
      return False
    if (self.wait != other.wait):
      return False
    if (self.next_action != other.next_action):
      return False
    #print self.name, '|', self.group(), other.group()
    # Don't compare translate if either task is waiting
    if (not self.is_wait() and not other.is_wait()):
      if (self.translate != other.translate):
        #print self.name, '|', self.group(), other.group()
        return False
    if caldav:
      return True
    # Optional checks:
    # Note not possible for caldav
    # start, starttext
    #if (self.starttext is not None and other.starttext is not None):
    if (self.starttext != other.starttext):
      return False
    # repeat
    #if (self.repeat is not None and  other.repeat is not None):
    if (self.repeat != other.repeat):
      return False
    # is_onhold
    #if (self.is_onhold is not None and other.is_onhold is not None):
    if (self.is_onhold != other.is_onhold):
      return False
    # flow (no access, add later?)
    # is_permanent (no access - add later?)
    # is_header (no access from Caldav?)
    # is_checklist (not used)
    return True

  def __eq__(self, other):
    if isinstance(other, FileTodos):
      return self.is_equal(other)
    return NotImplemented

  def __ne__(self, other):
    result = self.__eq__(other)
    if result is NotImplemented:
      return result
    return not result

  def __lt__(self, other):
    # Check due
    if (self.due is None and other.due is not None):
      return False
    if (self.due is not None and other.due is None):
      return True
    if ((self.due is not None and other.due is not None) and self.due != other.due):
      return self.due < other.due

    # Check priorities
    if (self.priority is None and other.priority is not None):
      return False
    if (self.priority is not None and other.priority is None):
      return True
    if ((self.priority is not None and other.priority is not None) and self.priority != other.priority):
      # Note priroties in reverse
      return self.priority < other.priority

    # Check wait
    if (self.is_wait() and not other.is_wait):
      return False
    if (not self.is_wait() and other.is_wait):
      return True

    return self.name < other.name

  def update(self, task, due=False, note=False, priority=False, wait=False, recursive=False, caldav=False, previous=None, caldavsource=False):
    # Also update FileTodo.__eq__
    # To stop passing all of the above around...:
    if previous is not None:
      due = (task.due != previous.due) or (task.alarm != previous.alarm) or due
      note = (task.note != previous.note) or note
      next_action = (task.next_action != previous.next_action)
      #next_action = True
      #print '['+previous.next_action+']', '['+task.next_action+']'
      priority = (task.priority != previous.priority) or priority
      wait = (task.wait != previous.wait) or wait
      # new:
      #starttext = (task.starttext is not None and previous.starttext is not None) and (task.starttext != previous.starttext)
      #repeat = (task.repeat is not None and previous.repeat is not None) and (task.repeat != previous.repeat)
      #is_onhold = (task.is_onhold is not None and previous.is_onhold is not None) and (task.is_onhold != previous.is_onhold)
      translate = False
      if (not task.is_wait() and not previous.is_wait()):
        translate = (task.translate != previous.translate)
  
      # Deal with updates on tasks from caldav data (i.e. ensure below are False)
      starttext = (task.starttext != previous.starttext) and (not caldavsource)
      repeat = (task.repeat != previous.repeat) and (not caldavsource)
      is_onhold = (task.is_onhold != previous.is_onhold) and (not caldavsource)
      #print 'caldavsource', caldavsource, starttext, repeat, is_onhold, task.name

    found = None
    #if self.name == task.name:
    if self.is_same_task(task):
      detail = ''
      if priority:
        detail = detail + ' priority: %(old)s -> %(new)s' % {
          'old': prioritystring(self.priority, shownone=True),
          'new': prioritystring(task.priority, shownone=True),
        }
        self.priority = task.priority
      if due:
        detail = detail + ' due: %(old)s -> %(new)s, alarm: %(aold)s -> %(anew)s' % {
          'old': '[empty]' if self.due is None else self.due.strftime('%y%m%d%H%M%z'),
          'new': '[empty]' if task.due is None else task.due.strftime('%y%m%d%H%M%z'),
          'aold': '[empty]' if self.alarm is None else self.alarm.strftime('%y%m%d%H%M%z'),
          'anew': '[empty]' if task.alarm is None else task.alarm.strftime('%y%m%d%H%M%z'),
        }
        self.due = task.due
        self.alarm = task.alarm
        # If due becomes None any start is now no longer relevant so ensure it is also cleared
        # Might need to do this for alarm too?  bit complicated...
        if (self.due is None and self.starttext is not None):
          detail = detail + ' start: %(old)s -> [empty] (enforced)' % {
            'old': '[empty:'+str(self.starttext)+']' if (self.starttext is None or self.starttext == '') else ' + '.join(self.starttext.splitlines()),
          }
          self.starttext = None
      if wait:
        detail = detail + ' wait: %(old)s -> %(new)s' % {
          'old': '[empty:'+str(self.wait)+']' if (self.wait is None or self.wait == '') else self.wait,
          'new': '[empty:'+str(task.wait)+']' if (task.wait is None or task.wait == '') else task.wait
        }
        self.wait = task.wait
      # asc 131203
      # if translate:
      #   detail = detail + ' translate: %(old)s -> %(new)s' % {
      #     'old': '[empty:'+str(self.translate)+']' if (self.translate is None or self.translate == '') else self.translate,
      #     'new': '[empty:'+str(task.translate)+']' if (task.translate is None or task.translate == '') else task.translate
      #   }
      #   self.translate = task.translate
      if note:
        detail = detail + ' note: %(old)s -> %(new)s' % {
          'old': '[empty:'+str(self.note)+']' if (self.note is None or self.note == '') else ' + '.join(self.note.splitlines()),
          'new': '[empty:'+str(task.note)+']' if (task.note is None or task.note == '') else ' + '.join(task.note.splitlines()),
        }
        self.note = task.note
      # new
      if is_onhold:
        detail = detail + ' hold: %(old)s -> %(new)s' % {
          'old': '[empty:'+str(self.is_onhold)+']' if (self.is_onhold is None or self.is_onhold == '') else self.is_onhold,
          'new': '[empty:'+str(task.is_onhold)+']' if (task.is_onhold is None or task.is_onhold == '') else task.is_onhold
        }
        self.is_onhold = task.is_onhold
      if starttext:
        detail = detail + ' start: %(old)s -> %(new)s' % {
          'old': '[empty:'+str(self.starttext)+']' if (self.starttext is None or self.starttext == '') else ' + '.join(self.starttext.splitlines()),
          'new': '[empty:'+str(task.starttext)+']' if (task.starttext is None or task.starttext == '') else ' + '.join(task.starttext.splitlines()),
        }
        self.starttext = task.starttext
      if repeat:
        detail = detail + ' repeat: %(old)s -> %(new)s' % {
          'old': '[empty:'+str(self.repeat)+']' if (self.repeat is None or self.repeat == '') else ' + '.join(self.repeat.splitlines()),
          'new': '[empty:'+str(task.repeat)+']' if (task.repeat is None or task.repeat == '') else ' + '.join(task.repeat.splitlines()),
        }
        self.repeat = task.repeat
      if next_action:
        detail = detail + ' next action: %(old)s -> %(new)s' % {
          'old': '[empty:'+str(self.next_action)+']' if (self.next_action is None or self.next_action == '') else ' + '.join(self.next_action.splitlines()),
          'new': '[empty:'+str(task.next_action)+']' if (task.next_action is None or task.next_action == '') else ' + '.join(task.next_action.splitlines()),
        }
        self.next_action = task.next_action

      #self.sequence_increment()
      if caldav:
        caltype = 'caldav'
      elif recursive:
        caltype = 'file'
      else:
        caltype = 'active'
      updated = False
      if caldav:
        # Assumes have previous
        if (due or note or priority or wait or translate or next_action):
          from CaldavClient import ical_event_update
          ical_event_update(self, due=due, note=note, priority=priority, wait=wait, translate=translate, previous=previous, next_action=next_action)
          updated = True
      else:
        updated = True
      if updated:
        report(colour.yellow + 'Updating task in' + colour.end + ' ' + colour.yellowbright + caltype + '|' +  '|'.join(self.parents) + colour.yellow + ':' + colour.end + ' ' + self.name + colour.grey + detail + colour.end)
      else:
        report(colour.yellow + 'Updating task in' + colour.end + ' ' + colour.yellowbright + caltype + '|' +  '|'.join(self.parents) + colour.yellow + ' not required and '+ colour.yellowbright +'skipped' + colour.end + ' ' + self.name + colour.grey + detail + colour.end)
        
      found = self
    else:
      for child in self.children:
        found = child.update(task, due=due, note=note, priority=priority, wait=wait, recursive=True, caldav=caldav, previous=previous, caldavsource=caldavsource)
        if found is not None:
          break
    if ((not recursive) and (not caldav)):
      self.make_modified(found)
    return found

  def make_modified_parents(self, task=None):
    if task is None:
      task = self
    if len(self.parents) > 1:
      self.parent.make_modified_parents(task=task)
    elif len(self.parents) == 1:
      self.make_modified(task=task)
    return

  def check_for_modified_children(self, root=True):
    modified = False
    if self.modified:
      modified = True
    for child in self.children:
      modified = modified or child.check_for_modified_children(root=False)
    if root and modified:
      self.set_modified()
    return modified

  def set_modified(self, task=None):
    if task is not None:
      name = task.name
    else:
      name = '[not provided]'
    if len(self.parents) > 0:
      parentstr = self.parents[-1]
    else:
      parentstr = '[parent unknown]'
    report(colour.magenta+'Marking modified ' + parentstr + '|' + self.name + ' for task ' + name + colour.end)
    self.modified = True

  def make_modified(self, task):
    def to_mark(current, task):
      if len(current.parents) == 0:
        return False
      return (task.parents[1] == current.name and task.parents[0] == current.parents[0])

    if len(task.parents) < 2:
      return
    if to_mark(self, task): 
      if not self.modified:
        self.set_modified(task)
    else:
      for child in self.children:
        child.make_modified(task)

  def child_names(self):
    names = []
    for child in self.children:
      names.append(child.name)
    return names

  def has_children(self):
    if len(self.children) > 0:
      return True
    return False

  def is_sequential(self):
    return self.flow == 'sequential'

  def set_wait(self, string=None):
    if string is None:
      string = 'wait'
    self.wait = string
    for child in self.children:
      child.set_wait(string)

  def set_updated(self, follow=True):
    self.updated = True
    if follow:
      for child in self.children:
        child.set_updated(follow=follow)

  def is_translate(self):
    if self.translate is not None:
      if len(self.translate) > 0:
        return True
    return False

  def is_wait(self):
    if self.wait is not None:
      if len(self.wait) > 0:
        return True
    return False

  def is_available(self):
    if self.is_onhold:
      return False
    if self.error:
      return False
    #if self.is_wait():
    #  return False
    if self.start is not None:
      if self.start > universe.now:
        return False
    return True

  def is_expired(self):
    if self.expire is not None:
      if self.expire <= universe.now:
        return True
    return False

  def is_active(self):
    # Exclude the root and projects
    if self.level <= 0:
      return False
    if self.is_header:
      return False
    if not self.is_available():
      return False
    if self.parent.is_wait():
      # Only include highest wait 
      return False
    #if (self.parent.is_translate_header() and self.parent.is_wait()):
    #  # Note onhold wipes out children anyway - here wait is special case
    #  return False
    #if ( len(self.translate) > 0 and len(self.parent.translate) == 0 ):
    if self.is_translate_header():
      # Header of aux list
      # Not great returning True here
      return True
    # Clause for grouped / lists
    if ((not self.is_checklist) and (self.has_children())):
      return False
    # Restricted to next actions, when sequential
    return True

  def find_all_names(self, todos=None):
    if todos == None:
      todos = []
    if not self.error:
      if self.level >= 1:
        todos.append(self.name)
      for child in self.children:
        todos = child.find_all_names(todos)
    return todos

  def find_all_tasks(self, todos=None):
    if todos == None:
      todos = []
    if not self.error:
      if self.level >= 1:
        todos.append(self)
      for child in self.children:
        todos = child.find_all_tasks(todos)
    return todos

  def find_all_task_occurances(self, task, occurances=None):
    if occurances == None:
      occurances = 0
    if self.is_same_task(task):
      occurances +=1
      #report('  DUPLICATE CALDAV: ' + str(occurances) + ' ' + task.name)
    for child in self.children:
      occurances = child.find_all_task_occurances(task, occurances)
    return occurances

  def find_active(self, active=None):
    if active == None:
      active = []
    if self.is_active():
      active.append(self)
      self.active = True
    is_sequential = self.is_sequential()
    for child in self.children:
      if child.is_completed:
        continue
      if not child.is_available():
        if is_sequential:
          break
        continue
      active = child.find_active(active)
      if is_sequential:
        break
    return active

  def is_valid_task(self):
    if self.level <= 0:
      return False
    if self.is_header:
      return False
    if self.is_onhold:
      return False
    if self.error:
      return False
    return True

  def find_next_actions(self, set_updated=True, updated=None):
    #if 'Meshing ' in self.name:
    #  verb=True
    #else:
    #  verb=False
    if updated is None:
      updated = []
    next_action = self.find_next_action()
    #if verb: print self.name + ': ['+str(self.next_action)+']', '['+str(next_action)+']'
    if self.next_action != next_action:
      self.next_action = next_action
      if set_updated:
        self.set_updated(follow=False)
        updated.append(self.name)
        #print '  UPDATED', self.name
        #print self.name + ': ['+str(self.next_action)+']', '['+str(next_action)+']'
    for child in self.children:
      child.find_next_actions(set_updated=set_updated, updated=updated)
    return updated

  def find_next_action(self):
    next_action = None
    if self.level <= 0:
      return None
    if self.parent.is_sequential():
      neighbours = self.parent.children
      found = False
      for neighbour in neighbours:
        if found:
          if neighbour.is_valid_task():
            next_action = neighbour
            break
        elif neighbour.name == self.name:
          found = True
    if next_action is None:
      return self.parent.find_next_action()
    else:
      return next_action.name

  #  next_actions = []
  #  if len(self.parents) == 0:
  #    return next_actions
  #  p = self.parents[-1]
  #  if not p.is_sequential():
  #    return next_actions
      

  def find_error(self, error=None):
    if error == None:
      error = []
    if self.error:
      error.append(self)
    for child in self.children:
      error = child.find_error(error)
    return error

  def show_error(self, show_notes=False):
    errors = self.find_error()
    if len(errors) == 0: return
    report(colour.redbright + 'ERROR' + colour.end)
    for task in errors:
      report(task.to_string(indentnone=True, notes=show_notes, show_where=True), forced=True)
    
  def is_important(self):
    return (self.priority is not None)

  def is_due_on_day(self, day):
    if self.due is None:
      return False
    if self.due.year != day.year:
      return False
    if self.due.month != day.month:
      return False
    if self.due.day != day.day:
      return False
    return True

  def is_overdue(self):
    if self.due is None:
      return False
    return universe.now > self.due 

  def is_due_today(self):
    return self.is_due_on_day(universe.now)

  def is_due_tomorrow(self):
    return self.is_due_on_day(universe.now + timedelta(days=1))
    
  def is_overdue_yesterday_or_past(self):
    return (self.is_overdue() and (not self.is_due_today()))

  def is_overdue_today_tomorrow_important(self):
    return (self.is_overdue() or self.is_due_today() or self.is_due_tomorrow() or self.is_important())

  def make_due_today(self, displacement=0, avoid_weekends=False):
    new_due = None
    new_start = None
    new_alarm = None
    detail = ''
    # shift from now time to due time, all today
    #shift = ((self.due.hour - universe.now.hour) * 60 + (self.due.minute - universe.now.minute)) * 60 + self.due.second - universe.now.second
    #new_due = universe.now + timedelta(seconds=shift)

    if self.repeat == 'random':
      new_due = universe.now.replace(second=0, microsecond=0) + calculate_delta('random')
    else:
      new_due = universe.now.replace(hour=self.due.hour, minute=self.due.minute, second=0, microsecond=0)

    # Apply displacement days
    new_due = new_due + timedelta(days=displacement)

    new_due = do_avoid_weekend(new_due, avoid_weekends=avoid_weekends)

    # Update start time
    if (self.starttext is not None and len(self.starttext) > 0):
      string = self.starttext
      if is_relative_date(string):
        d = calculate_delta(string)
        if d is not None:
          new_start = new_due - d
    # Update alarm
    if self.alarm is not None:
      if self.alarmtext is not None:
        self.alarm, allday = parsedate(self.alarmtext, reference=new_due, alarm=True, allday=self.allday())
      elif self.allday():
        # Warning for day events 1800 - 1000 = 8 hours
        new_alarm = new_due + universe.defaulttime.alldaydiff
      else: 
        # Default warning of an hour
        new_alarm = new_due + universe.defaulttime.diff
    detail = detail + ' due: %(old)s -> %(new)s' % {
      'old': '[empty]' if self.due is None else self.due.strftime('%y%m%d%H%M%z'),
      'new': '[empty]' if new_due is None else new_due.strftime('%y%m%d%H%M%z')
    }
    self.due = new_due
    if new_start is not None:
      detail = detail + ' start: %(old)s -> %(new)s' % {
        'old': '[empty]' if self.start is None else self.start.strftime('%y%m%d%H%M%z'),
        'new': '[empty]' if new_start is None else new_start.strftime('%y%m%d%H%M%z')
      }
      self.start = new_start
    if new_alarm is not None:
      detail = detail + ' alarm: %(old)s -> %(new)s' % {
        'old': '[empty]' if self.alarm is None else self.alarm.strftime('%y%m%d%H%M%z'),
        'new': '[empty]' if new_alarm is None else new_alarm.strftime('%y%m%d%H%M%z')
      }
      self.alarm = new_alarm
    report(colour.yellow + 'Update due to today for important task in' + colour.end + ' ' + colour.yellowbright + '|'.join(self.parents) + colour.yellow + ':' + colour.end + ' ' + self.name + colour.grey + detail + colour.end)
    self.make_modified_parents()
    return

  def prioritycurrent(self, caldav=False):
    # Make tasks with a priority that have a due time in the previous days or past,
    # due today at the same time
    # Only applied to current active list?
    #print self.name
    if ((self.is_important() or self.current) and self.is_overdue_yesterday_or_past()):
      #print 'HERE', self.name 
      try:
        # Check here if in skipweekendlists
        avoid_weekends = ((self.group(masked=False) in universe.skipweekendlists) or self.avoidweekends)
        # self.make_due_next_work_day()
        self.make_due_today(avoid_weekends=avoid_weekends)
        # state.aiyo.make_modified(self)
        if caldav:
          from CaldavClient import ical_event_update
          ical_event_update(self, due=True)
        else:
          self.set_modified()
      except Exception, e:
        out = os.linesep + ' Task: ' + self.name + ' ' + self.due.strftime('%y%m%d%H%M')
        error('Error in making a priority task current, exception: ' + str(e) + out)
        pass

  def to_string(self, reformat=False, indentfull=False, indentnone=False, notes=True, show_where=False, show_next_action=False, show_translate_inheritance=False):
    iro = generate_mono(reformat)
    contentlist = []
    if self.lines is not None:
      for i in range(len(self.lines)):
        contentlist.append('%(num)6d %(indent)2d %(content)s' % { 'num':i, 'indent':indentation(self.lines[i]), 'content':self.lines[i] })
    content = os.linesep.join(contentlist)

    if not notes:
      note = ''
    elif self.note is None:
      note = ''
    elif len(self.note) == 0:
      note = ''
    else:
      note = os.linesep + os.linesep.join([ ' ' * 4 + notelines for notelines in self.note.splitlines() ])
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

    out_priority = prioritystring(self.priority, spacer=True)


    translate = ''
    if self.translate is not None:
      if self.is_translate():
        if (self.parent is None or show_translate_inheritance):
          translate = ' =' + self.translate
        else:
          if not self.parent.is_translate():
            translate = ' =' + self.translate
    
    #print self.name, self.translate, translate, self.parent
    
    if show_where:
      parents = ' ' + (iro.grey+':'+iro.end).join([ iro.grey + x + iro.end for x in self.parents ])
    else:
      parents = ''

    if show_next_action and (self.next_action is not None) and (len(str(self.next_action)) > 0):
      next_action = ' ' + iro.green + universe.next_char + str(self.next_action) + iro.end
    else:
      next_action = ''

    if self.is_overdue():
      highlight_name = iro.redbright
    elif self.is_due_today():
      highlight_name = iro.red
    elif self.is_due_tomorrow():
      highlight_name = iro.yellow
    elif self.priority is not None:
      highlight_name = iro.yellow
    else:
      highlight_name = ''

    options = '''\
%(spacer)s%(start)s%(divider)s%(due)s%(expire)s%(alarm)s%(priority)s%(repeat)s%(translate)s%(checklist)s%(flow)s%(header)s%(waitonrepeat)s%(permanent)s%(current)s%(avoidweekends)s%(wait)s%(paused)s%(completed)s%(parents)s%(next)s%(error)s''' \
      % {
        'start': '' if (self.starttext is None or len(self.starttext) == 0) else iro.cyan + self.starttext + iro.end,
        'due': iro.blue + out_due + iro.blue,
        'alarm': iro.red + out_alarm + iro.end,
        'priority': iro.redbright + out_priority + iro.end,
        'divider': '' if (self.starttext is None or len(self.starttext) == 0 ) else iro.grey + ':' + iro.end,
        'repeat': '' if (self.repeat is None or len(self.repeat) == 0) else ' ' + iro.magenta + self.repeat + iro.end,
        'expire': '' if (self.expiretext is None or len(self.expiretext) == 0) else ' ' + iro.magenta + self.expiretext + iro.end,
        'spacer': '' if ((self.starttext is None or len(self.starttext) == 0) and (len(out_due) == 0)) else ' ',
        'translate': iro.yellow + translate + iro.end, 
        'checklist': iro.yellow+' checklist'+iro.end if self.is_checklist else '',
        'header': iro.yellow+' header'+iro.end if self.is_header else '',
        'completed': iro.green+' completed'+iro.end if self.is_completed else '',
        'paused': iro.blue+' hold'+iro.end if self.is_onhold else '',
        'permanent': iro.magenta+' permanent'+iro.end if self.is_permanent else '',
        'current': iro.magenta+' current'+iro.end if self.current else '',
        'avoidweekends': iro.magenta+' avoidweekends'+iro.end if self.avoidweekends else '',
        'wait': ' ' + iro.blue+self.wait+iro.end if self.is_wait() else '',
        'waitonrepeat': iro.blue+' waitonrepeat'+iro.end if self.waitonrepeat else '',
        'error': iro.redbright+' ERROR'+iro.end if self.error else '',
        'flow': iro.magenta+' ' + self.flowtext+iro.end if self.flowtext is not None else '',
        'parents': parents,
        'next': next_action,
      }
    text = '''%(name)s%(spacer)s%(options)s%(note)s''' \
      % {
        'name': highlight_name + self.name + iro.end,
        'spacer': '' if len(options) == 0 else ' ',
        'options': options,
        'note': note,
      }

    if indentnone:
      indent = 2
    else:
      indentmod = 0
      if indentfull:
        indentmod = 2
      if reformat:
        indentmod = -1
      indent = (self.level + indentmod) * 2

    text = os.linesep.join([ ' ' * indent + notelines for notelines in text.splitlines() ])
    return text

  def __str__(self):
    return self.to_string()

  def find_children(self):
    for i in range(len(self.childblocks)):
      block = self.childblocks[i]
      
      parents = []
      for p in self.parents + [self.name]:
        parents.append(p)

      child = FileTodos(self.lines[block[0]:block[1]], parents = parents, number=i+1, parent=self, translate=self.translate)
      self.add_child(child)

  def find_note(self):
    if self.lines is None: return ''
    if len(self.lines) == 0: return ''
    if self.level == 0:
      if indentation(self.lines[0]) < self.level + 1: return ''
    else:
      if len(self.lines) == 1: return ''
      if indentation(self.lines[1]) < self.level + 1: return ''
    note = []
    for i in range(len(self.lines)):
      if ((self.level > 0) and (i == 0)): continue
      if indentation(self.lines[i]) < self.level + 1: break
      note.append(re.sub('^'+ ' ' * (self.level + 1) * 2, '', self.lines[i]))
    if len(note) == 0:
      return ''
    return os.linesep.join(note)

  def set_note(self, obj):
    self.note = obj

  def add_child(self, obj):
    obj.parent = self
    self.children.append(obj)

  def set_block(self, obj):
    self.block = obj

  def set_childblocks(self, obj):
    self.childblocks = obj

  def show_tree(self, indentfull=True, notes=True, activeonly=False, availableonly=False):
    if ((activeonly or availableonly) and not self.is_available()): return
    if (activeonly and not self.is_active()): return
    report(self.to_string(indentfull=indentfull, notes=notes), forced=True)
    for child in self.children:
      child.show_tree(indentfull=indentfull, notes=notes, activeonly=activeonly, availableonly=availableonly)

  def reformat(self):
    output = ''
    if self.level > 0:
      output = self.to_string(reformat=True) + os.linesep
    
    for child in self.children:
      output = output + child.reformat()

    if (self.level == 0 and self.filenotes is not None):
      output = output + os.linesep.join(['',''] + self.filenotes)
    return output
  
  def write(self, name=None, category=None):
    if not self.modified: return False
    if name is None:
      name = self.name
    if len(self.parents) > 0:
      category = self.parents[0]
    if category is None:
      filename = universe.dataroot + name
    else:
      filename = universe.dataroot + category + '/'
      if not os.path.exists(filename):
        # Could be case here where file exists in place of foldername, this will cause trouble!
        os.mkdir(filename)
      filename = filename + name
    repo_in = os.path.exists(filename)
    report(colour.grey + 'Writing ' + colour.blue + category + colour.grey + '/' + colour.yellowbright + name + colour.end + ' ' + colour.grey + '(to' + colour.grey + ' ' + filename + colour.grey + ')' + colour.end)
    if not universe.dry:
      f = open(filename, 'w')
      f.write(self.reformat().encode('utf-8'))
      f.close()
      if not repo_in:
        repo_add(filename)
    if self.is_empty():
      report('  ' + colour.grey + 'Removing ' + colour.blue + category + colour.grey + '/' + colour.yellowbright + name + colour.end + ' ' + colour.grey + '(' + colour.grey + filename + colour.grey + ')' + colour.end)
      if not universe.dry:
        try:
          if os.path.exists(filename):
            os.remove(filename)
            repo_remove(filename)
        except:
          pass
    return True

  def identify_blocks(self, start=None, end=None):
    lines_to_excluded_section = 2
    debug = False
    #debug = (self.name == 'finance')

    if self.lines is None:
      return []
    def add_block(r):
      blocks.append(r)
      if debug: print '    ', r

    blocks = []
    if start is None:
      start = 0
    if end is None:
      end = len(self.lines)
    if len(self.lines) <= 1: return blocks
    r = [ -1, -1 ]
    blanks = 0
    for i in range(start, end):
      line = self.lines[i]
      indent = indentation(line)
      if debug: print i, blanks, r, indent, line

      if len(line) == 0:
        blanks += 1
        continue
      # Indent is of current level

      if indent == self.level:

        # Existing block
        if (r[0] > -1 and  r[1] == -1):
          if debug: print 'complete', blanks, blanks >= 2
          r[1] = i
          add_block(r)
          r = [ -1, -1 ]

        if r[0] == -1:
          if debug: print 'new'
          # If 2 or more previous blanks AND now indent = level
          if blanks >= lines_to_excluded_section: break
          # Start new block
          if len(line.strip()) > 0:
            r[0] = i

      blanks = 0
    # Add concluding block, if one has begun
    if ((r[0] > -1) and (r[1] == -1)):
      r[1] = i + 1
      add_block(r)
    if debug: print self.name, blocks
    if debug:
      report('XXXX'+ self.name)
      print blocks
      if len(blocks) > 0: print os.linesep.join(self.lines[blocks[-1][0]:blocks[-1][1]])
      sys.exit(1)
    return blocks

  def interpret_task(self, title):
    sections = title.split('  ', 1)
    if len(sections) == 2:
      # Check if len(sections[1]) > 0?
      self.name = sections[0]
      title = sections[1]
    else:
      self.name = title
      title = ''

    words = title.split(' ')
    titlelist = []
    for word in words:
      # NLP not working here, as cannot apply set_modified at this early point of parsing,
      #   would need to mark to update aiyo at a later stage, once the FileTodo object
      #   has been set up.
      if re.match('^today$', word):
        self.duetext = universe.now.strftime('%y%m%d')
        self.set_modified(self)
      elif re.match('^tomorrow$', word):
        self.duetext = (universe.now + timedelta(days=1)).strftime('%y%m%d')
        self.set_modified(self)
      elif word in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] \
                 + ['mon', 'tues', 'tue', 'wed', 'thurs', 'thu', 'thur', 'fri', 'sat', 'sun']:
        self.duetext = next_weekday(word)
        self.set_modified(self)
      elif re.match('^\d*(day|week|month|year)s*$', word):
        self.duetext = next_increment(word)
        self.set_modified(self)
      elif re.match('^\d{6}$', word):
        self.duetext = word
      elif re.match('^\d{10}$', word):
        self.duetext = word
      elif re.match('^\d{6}:$', word):
        self.starttext = word[:-1]
      elif re.match('^\d{10}:$', word):
        self.starttext = word[:-1]
      elif re.match('^\w+:\d{6}$', word):
        self.starttext, self.duetext = word.rsplit(':', 1)
      elif re.match('^\w+:\d{10}$', word):
        self.starttext, self.duetext = word.rsplit(':', 1)
      elif re.match('^\w+:$', word):
        self.starttext = word[:-1]
      elif re.match('^!\d{6}$', word):
        self.alarmtext = word[1:]
      elif re.match('^!\d{10}$', word):
        self.alarmtext = word[1:]
      elif (re.match('^!\w+$', word) and is_relative_date(word)):
        self.alarmtext = word[1:]
      elif re.match('^!$', word):
        self.priority = 9
      elif re.match('^!!$', word):
        self.priority = 5
      elif re.match('^!!!$', word):
        self.priority = 1
      elif re.match('^every\w+$', word):
        self.repeat = word
      elif re.match('^after\w+$', word):
        self.repeat = word
      elif re.match('^random$', word):
        self.repeat = word
      elif word in ['decennially', 'biennially', 'annually', 'monthly', 'fortnightly', 'weekly', 'daily']:
        self.repeat = word
      elif re.match('^expire\w+$', word):
        self.expiretext = word
      elif re.match('^checklist$', word):
        self.is_checklist = True
      elif re.match('^sequential$', word):
        self.flowtext = 'sequential'
      elif re.match('^parallel$', word):
        self.flowtext = 'parallel'
      elif re.match('^header$', word):
        self.is_header = True
      elif re.match('^completed$', word):
        self.is_completed = True
      elif re.match('^paused$', word):
        self.is_onhold = True
      elif re.match('^onhold$', word):
        self.is_onhold = True
      elif re.match('^hold$', word):
        self.is_onhold = True
      elif re.match('^permanent$', word):
        self.is_permanent = True
      elif re.match('^avoidweekends$', word):
        self.avoidweekends = True
      elif re.match('^current$', word):
        self.current = True
      #elif re.match('^everpresent$', word):
      #  self.is_everpresent = True
      elif re.match('^waitonrepeat$', word):
        self.waitonrepeat = True
        #self.wait = 'wait'
      elif re.match('^wait$', word):
        self.wait = word
      elif re.match('^ERROR$', word):
        self.error = True
      # asc
      elif re.match('^=\w+$', word):
        self.translate = word[1:]
      elif re.match('^@\w+$', word):
        self.sublist = word[1:]
      else:
        titlelist.append(word)
      if self.flowtext is not None:
        self.flow = self.flowtext

