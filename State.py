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
import re
import pickle

from Support import error, report
from Support import repo_update
from FileTodo import FileTodos, tasklist_read
from Events import Events

def caldav_load(calendarname):
  from CaldavClient import calendar_load
  from CalTodo import CalTodo
  # Try needed for case when Apache is restarted, exception [Errno 104] Connection reset by peer
  try:  
    client, calendar = calendar_load(calendarname)
    events = []
    calendarevents = calendar.events()
    for calendarevent in calendarevents:
      event = CalTodo(calendarevent, calendarname)
      if not event.readstat:
        return None, None, None
      if event.is_complete():
        report(colour.red + 'Removed completed event: ' + colour.end + event.parents[0] + '|' + event.name + colour.end)
        calendarevent.delete()
      elif event.is_valid():
        #new = FileTodos(lines=task.reformat().splitlines(), parents=match.parents + [match.name], parent=match)
        # Note parents only contains top grouping here, and also parent might be wrong - not relevent in the CalTodos?
        translate = None
        if (event.groupname in universe.auxlists and not event.is_wait()):
          translate = event.groupname
        fevent = FileTodos(lines=event.reformat().splitlines(), parents=event.parents, translate=translate, uid=event.uid, caldav=True, next_action=event.next_action)
        #events.append(event)
        #if '  ' in event.name:
        #  ical_event_update(fevent)
        events.append(fevent)
    return client, calendar, events
  except:
    if universe.debug: raise
    pass
  return None, None, None

class State(object):
  def __init__(self, active=None, caldav=None, aiyo=None, load=False, generate=False, localonly=False, previous=None):
    self.active = None 
    self.caldav = None
    self.aiyo = None
    if active is None: active = []
    if caldav is None: caldav = []
    if aiyo is None: aiyo = []
    if load:
      self.active, self.caldav = self.load_from_file() 
      self.aiyo = aiyo
    elif generate:
      self.generate(active=active, caldav=caldav, aiyo=aiyo, localonly=localonly, previous=previous)
    else:
      self.active = Events(active, name='aiyo')
      self.caldav = Events(caldav, name='caldav')
      self.aiyo = aiyo

  def generate(self, active=None, caldav=None, aiyo=None, localonly=False, previous=None):
    aiyo = FileTodos(title='Todos')
    projects = []
    categories = []
    categories = [ f for f in os.listdir(universe.dataroot) if (os.path.isdir(os.path.join(universe.dataroot,f)) and not f.startswith('.')) ]
    for category in categories:
      category_projects = []
      category_projects = [ f for f in os.listdir(os.path.join(universe.dataroot, category)) if (os.path.isfile(os.path.join(universe.dataroot, category, f)) and not f.startswith('.')) ]
      category_todos = FileTodos(title=category, level=-1)
      for category_project in category_projects:
        tasks = tasklist_read(category_project, category)
        category_todos.add_child(tasks)
      aiyo.add_child(category_todos)

    if not localonly:
      caldav = []
      caldav_error = False
      for tasklistname in aiyo.child_names() + universe.auxlists:
        client, calendar, tasks = caldav_load(tasklistname)
        #print '  ',  tasklistname, client, calendar, tasks
        if (client is None or calendar is None or tasks is None):
          caldav_error = True
        else:
          caldav.extend(tasks)
      
      if caldav_error:
        self.caldav = None
      else:
        self.caldav = Events(caldav, name='caldav')

    active = aiyo.find_active()
    #print 'here_no update'
    aiyo.find_next_actions(set_updated=False)
    self.active = Events(active, name='aiyo')
    self.aiyo = aiyo

    if not localonly:
      self.sort_groups(previous=previous)
    # Create state
    #return State(active=active, caldav=todo_caldav, aiyo=todo_aiyo)

  def deduplicate(self, forced=False):
    from CaldavClient import ical_event_add, ical_event_delete
    duplicates_c = Events([], name='duplicates_caldav')
    duplicates_a = Events([], name='duplicates_aiyo')

    #names_aiyo = self.aiyo.find_all_names()
    tasks_aiyo = self.aiyo.find_all_tasks()
    #names_caldav = self.caldav.find_names()
    tasks_caldav = self.caldav.events
    #for name in names_aiyo:

    for task in tasks_aiyo:
      #if names_aiyo.count(name) > 1: 
      if self.aiyo.find_all_task_occurances(task) > 1:
        #if not duplicates_a.task_is_present(task):
        #if name not in duplicates_a:
        duplicates_a.add(task)
        # Ensure problematic tasks in aiyo are renamed in caldav too to prevent them being added back to aiyo on next run through (and then again being marked in error - continuously added to inbox...)
        if self.caldav.find_all_task_occurances(task) > 0:
          duplicates_c.add(task)
      # Dangerous for now...
      # if names_caldav.count(name) > 1: 
      #   if name not in duplicates_a:
      #     duplicates_a.append(name)

    #for name in names_caldav:
    #  if names_caldav.count(name) > 1: 
    #    if name not in duplicates_c:
    #      duplicates_c.append(name)
    #  if names_aiyo.count(name) > 1: 
    #    if name not in duplicates_c:
    #      duplicates_c.append(name)

    for task in tasks_caldav:
      if self.caldav.find_all_task_occurances(task) > 1:
        duplicates_c.add(task)
        #if not duplicates_c.task_is_present(task):
      #if self.aiyo.find_all_task_occurances(task) > 1:
      #  if not duplicates_c.task_is_present(task):
      #    # Should be _a below?
      #    duplicates_c.add(task)

    #names = names_aiyo
    #for name in names_caldav:
    #  if name not in names:
    #    names.append(name)

    tasks = Events([], 'alluniquetasks')
    tasks.extend(tasks_aiyo)
    for task in tasks_caldav:
      if not tasks.task_is_present(task):
        tasks.add(task)
    names = tasks.names

    if (duplicates_c.find_number() == 0 and duplicates_a.find_number() == 0):
      # No duplicates found!
      return True
    else:
      if not forced:
        # Not yet forced, drop out of processing and wait a bit...
        report(colour.red + 'Duplicates: ' + ', '.join(duplicates_c.find_names() + duplicates_a.find_names()) + colour.end)
        return False

    # Actual de-duplication process:
    # Deal with caldav duplicates
    error('Duplicates found, and persistent, processing now forced')
    if duplicates_c.find_number() > 0:
      duplicates = []
      for task in self.caldav.events:
        #report('DEDUP '+task.name+', '+str(task.parents[0]) +', '+str(duplicates_c.task_is_present(task)))
        if duplicates_c.task_is_present(task):
          duplicates.append(task)

      for task in duplicates:
        #report(colour.yellow + 'De-duplicating caldav task: ' + task.name + colour.end)
        # Temporarily in place
        error('De-duplicating caldav task: ' + task.name)
        ical_event_delete(task)
        renamed = False
        while task.name in names:
          if not renamed:
            task.name = task.name + ' '
            renamed = True
          task.name = task.name + '-'
        names.append(task.name)
        ical_event_add(task)
      # Doing above now, otherwise need to change to be done by name here
      #for task in duplicates_c.events:
      #  ical_event_delete(task)

    # Deal with aiyo duplicates
    if duplicates_a.find_number() > 0:
      error('Duplicates found in aiyo [UNTESTED], with names: ' + (os.linesep + '  ').join(['']+duplicates_a.names))
      duplicates = []
      for task in self.aiyo.find_all_tasks():
        if duplicates_a.task_is_present(task):
          duplicates.append(task)

      for task in duplicates:
        # Mark as error (superseded)
        # task.error = True
        # report(colour.yellow + 'Marking task in error: ' + task.to_string(reformat=True) + colour.end)
        # Actual deduplication:
        error('De-duplicating aiyo task: ' + task.name)
        renamed = False
        while task.name in names:
          if not renamed:
            task.name = task.name + ' '
            renamed = True
          task.name = task.name + '-'
        names.append(task.name)
        # Deduplication / mark as error end
        self.aiyo.make_modified(task)
    self.update_active()

    # De-duplication done, allow processing to continue
    return True

  def update_active(self):
    new_active = Events(self.aiyo.find_active(), name='aiyo')
    additions = Events(name='additions')
    removals = Events(name='removals')
    updated = Events(name='updated')
    for task in self.active.events:
      if not new_active.task_is_present(task):
        # Task has been removed
        removals.add(task)
    for task in new_active.events:
      if not self.active.task_is_present(task):
        # Task has been added
        additions.add(task)
    self.active = new_active
    for task in self.active.events:
      if task.updated:
        updated.add(task)
    return additions, removals, updated

  def show_active(self):
    report('Active tasks:')
    for i in range(len(self.active.events)):
      report('  ' + str(i+1) + ' ' + self.active.events[i].name.encode('utf-8'))

  def sort_groups(self, previous=None):
    if previous is None:
      previous = self
    if not self.is_valid():
      return
    for task in self.caldav.events:
      # If parent exists, group already known
      if task.parents[0] in self.aiyo.child_names(): continue

      parents = ['home']
      matches = []

      if task.parents[0] == 'wait':
        task.set_wait()
        matches = previous.active.find_tasks_by_name(name=task.name, check_is_wait=True)
      if len(matches) == 0:
        matches = previous.active.find_tasks_by_name(name=task.name)
      if len(matches) > 1:
        matches_again = []
        for match in matches:
          #print match.name, '|', match.parents[0], '|', match.group(), '|', not self.caldav.contains_task_by_name_group(match.name, match.parents[0])
          if not previous.caldav.contains_task_by_name_group(match.name, match.parents[0]):
            matches_again.append(match)
        if len(matches_again) == 1:
          parents = matches_again[0].parents
        else:
          error('Multiple matches to locate waiting task: ' + task.name +' defaulting to: home')
      elif len(matches) > 0:
        if len(matches[0].parents) > 0:
          parents = matches[0].parents

      task.parents = parents
      #report(colour.yellow + 'Wait task: ' + task.name + ' (identified to parent: ' + '|'.join(task.parents) + ')' + colour.end)

  def is_valid(self, localonly=False):
    if self.active is None:
      return False
    if self.aiyo is None:
      return False
    if not localonly:
      if self.caldav is None:
        return False
    return True

  def load_from_file(self):
    active, caldav = None, None
    if os.path.exists(universe.statefile):
      try:
        f = open(universe.statefile, 'rb' )
        active, caldav = pickle.load(f)
        f.close()
      except Exception, e:
        error('Error loading state file, exception: ' + str(e))
        pass
    return active, caldav 

  def clear_titleoptions(self):
    # Don't save options that caldav can't represent throughout time
    for task in self.caldav.events:
      task.clear_titleoptions()

  def save(self):
    #self.clear_titleoptions()
  
    #if universe.dry:
    #  return True
    try:
      f = open( universe.statefile, 'wb' )
      pickle.dump([self.active, self.caldav], f)
      f.close()
      return True
    except Exception, e:
      error('Error saving state file, exception: ' + str(e))
      pass
    return False

  def expire(self):
    for a in self.active.events:
      if not a.is_expired(): continue
      b = self.caldav.find_task(a)
      # Already removed from caldav, continue, aiyo should get updated 
      # in time (and avoids double remove/repeat)
      if b is None: continue
      try:
        # Remove from caldav, should then feed back into aiyo
        self.caldav.remove(b)
      except Exception, e:
        out =       os.linesep + '  State: ' + self.active.name + ' Task: ' + a.name + a.due.strftime('%y%m%d%H%M')
        out = out + os.linesep + '  State: ' + self.caldav.name + ' Task: ' + b.name + b.due.strftime('%y%m%d%H%M')
        error('Error in expiring task, exception: ' + str(e) + out)
        pass

  def prioritycurrent(self):
    for task in self.active.events:
      task.prioritycurrent()
    for task in self.caldav.events:
      task.prioritycurrent(caldav=True)

  def __str__(self):
    return self.to_string()

  def to_string(self):
    show_next_action=True
    return self.active.to_string(show_next_action=show_next_action) + os.linesep + self.caldav.to_string(show_next_action=show_next_action)

def state_generate():
  # Not used?
  todo_aiyo = FileTodos(title='Todos')
  projects = []
  categories = []
  categories = [ f for f in os.listdir(universe.dataroot) if (os.path.isdir(os.path.join(universe.dataroot,f)) and not f.startswith('.')) ]
  for category in categories:
    category_projects = []
    category_projects = [ f for f in os.listdir(os.path.join(universe.dataroot, category)) if (os.path.isfile(os.path.join(universe.dataroot, category, f)) and not f.startswith('.')) ]
    category_todos = FileTodos(title=category, level=-1)
    for category_project in category_projects:
      tasks = tasklist_read(category_project, category)
      category_todos.add_child(tasks)
    todo_aiyo.add_child(category_todos)

  todo_caldav = []
  for tasklistname in todo_aiyo.child_names() + universe.auxlists:
    client, calendar, tasks = caldav_load(tasklistname)
    if (client is None or calendar is None or tasks is None):
      return None
    todo_caldav.extend(tasks)

  active=todo_aiyo.find_active()

  # Create state
  return State(active=active, caldav=todo_caldav, aiyo=todo_aiyo)

def aiyo_write(state):
  change = False
  for category in state.aiyo.children:
    for project in category.children:
      stat = project.write()
      if stat:
        change = True
  if change:
    repo_update(commit=True)

# def tasks_same(a, b):
#   # Also update FileTodo.update
#   if (a.due != b.due):
#     return False
#   if (a.alarm != b.alarm):
#     return False 
#   if (a.note != b.note):
#     return False
#   if (a.priority != b.priority):
#     return False
#   if (a.wait != b.wait):
#     return False
#   return True

def time_regularise(time):
  if time is not None:
    try:
      time = universe.timezone.localize(time.replace(tzinfo=None))
    except:
      pass
  return time

def find_changes(state_a, state_b, changes=None, caldav=False):
  full_debug = False
  if changes is None:
    changes = []
  for a in state_a.events:
    # Time regularise step should be elsewhere / not necessary
    a.due = time_regularise(a.due)
    a.alarm = time_regularise(a.alarm)
    b = state_b.find_task(a)
    if b is None:
      # This is a new task in a, added above (and not in b)
      # report('Error, not found previous in ' + state_b.name + ' ' + a.name)
      # Note other case of b not in a not considered here
      continue
    b.due = time_regularise(b.due)
    b.alarm = time_regularise(b.alarm)
    try:
      #if (a.due != b.due) or (a.alarm != b.alarm) or (a.note != b.note) or (a.priority != b.priority):
      #if not tasks_same(a, b):
      #print a.name, b.name, a.starttext, b.starttext, a != b
      #if a != b:
      if (not a.is_equal(b, caldav=caldav)):
        if (universe.debug and full_debug):
          #print 'caldav', caldav
          if a.due != b.due:
            report('Change in due   time in ' + state_a.name + ' ' + a.name + ' ' + b.due.strftime('%y%m%d%H%M%S%z') + ' -> ' + a.due.strftime('%y%m%d%H%M%S%z'))
            # print a.due - b.due
            # #print a.due
            # #print b.due
            # print a.due
            # print b.due
            # print a.due.replace(tzinfo=None)
            # print a.due.replace(tzinfo=None)
            # print universe.timezone.localize(a.due.replace(tzinfo=None))
            # print universe.timezone.localize(b.due.replace(tzinfo=None))
          if a.alarm != b.alarm:
            report('Change in alarm time in ' + state_a.name + ' ' + a.name + ' ' + b.alarm.strftime('%y%m%d%H%M%S%z') + ' -> ' + a.alarm.strftime('%y%m%d%H%M%S%z'))
            #print a.alarm - b.alarm
            #print a.alarm
            #print b.alarm
          if a.note != b.note:
            report('Change in note in ' + state_a.name + ' ' + a.name + ' ' + b.note.encode('utf-8') + ' -> ' + a.note.encode('utf-8'))
          if a.priority != b.priority:
            report('Change in priority in ' + state_a.name + ' ' + a.name + ' ' + str(b.priority) + ' -> ' + str(a.priority))
          if a.wait != b.wait:
            report('Change in wait in ' + state_a.name + ' ' + a.name + ' ' + b.wait + ' -> ' + a.wait)
          if a.repeat != b.repeat:
            report('Change in repeat in ' + state_a.name + ' ' + a.name + ' ' + str(b.repeat) + ' -> ' + str(a.repeat))
          #print a.type, b.type
        if a.name not in changes:
          changes.append(a)
    except Exception, e:
      out =       os.linesep + '  State: ' + state_a.name + ' Task: ' + a.name + a.due.strftime('%y%m%d%H%M')
      out = out + os.linesep + '  State: ' + state_b.name + ' Task: ' + b.name + b.due.strftime('%y%m%d%H%M')
      error('Error finding changes to state, exception: ' + str(e) + out)
      pass
  return changes

def diff(state, state_previous):
  debug=False
  state.expire()
  state.prioritycurrent()

  # changes
  changes = find_changes(state.active, state_previous.active)
  changes = find_changes(state.caldav, state_previous.caldav, changes=changes, caldav=True)

  # Check changes to aiyo, for later application to caldav
  caldav_to_add = Events(name='caldav_to_add')
  caldav_to_remove = Events(name='caldav_to_remove')
  # deletions
  if debug: report('AIYO -> CALDAV check', debug=True)
  for task in state_previous.active.events:
    if not state.active.task_is_present(task):
      # Task has been removed, remove from caldav
      caldav_to_remove.add(task)
  # additons
  for task in state.active.events:
    if not state_previous.active.task_is_present(task):
      # Task has been added, add to caldav
      caldav_to_add.add(task)

  if debug: report('CALDAV -> AIYO', debug=True)
  # Check changes to caldav, apply to aiyo
  # deletions
  #update_active_required = False
  update_active_required = True
  for task in state_previous.caldav.events:
    if not state.caldav.task_is_present(task):
      update_active_required = True
      state.active.remove(task)
      # recurrance
      new = state.aiyo.recur(task)
      if new is not None:
        if new.is_active():
          report(colour.magenta + '  recurring task is still active' + colour.end, debug=True)
          state.active.add(new)
          caldav_to_add.add(new)
      # Checks if active and adds back in here (no need to wait for next run to mop up) 
      #state.aiyo.remove(task)
  if update_active_required:
    #state.show_active()
    if debug: report('  Updating ACTIVE', debug=True)
    additions, removals, updated = state.update_active()
    #state.show_active()
  # additons
  for task in state.caldav.events:
    #if task.group() == 'wait':
    #  report(task.name + '|' +  task.parents[0])
    #  for t in state_previous.caldav.events:
    #    report('  ' + t.name + ' | ' + t.parents[0])
    if not state_previous.caldav.task_is_present(task):
      # Ensure trigger due is also applied to due
      # Now done above
      #ical_event_update(task, due=True)
      #update_active_required = True
      if debug: print 'new', task.to_string(reformat=True, show_where=True)
      state.active.add(task)
      state.aiyo.add(task)

  # Extra step to deal with additions and removals in recur above - do better?
  for task in removals.events:
    caldav_to_remove.add(task)
    report(colour.red + 'Task since removed from active: ' + task.name + ' (group: ' + task.group() +')' + colour.end)
  for task in additions.events:
    caldav_to_add.add(task)
    report(colour.red + 'Task since added to active: ' + task.name + ' (group: ' + task.group() +')' + colour.end)

  if debug: report('AIYO -> CALDAV', debug=True)
  # Changes to aiyo, apply to caldav
  for task in caldav_to_remove.events:
    state.caldav.remove(task)
  for task in caldav_to_add.events:
    state.caldav.add(task)
    # Changes to this task are dealt with here, clear updated flag for now
    task.updated = False

  if debug: report('SANITY', debug=True)
  # Sanity check, mopping up (SHOULD DO NOTHING!)
  for task in state.active.events:
    if not state.caldav.task_is_present(task):
      report(colour.red + 'Sanity: Task missing from caldav: ' + task.name + ' (group: ' + task.group() +')' + colour.end)
      # Task in active, not in caldav, add to caldav
      # Note the optional fields like starttext, hold, etc could be problematic in the sanity check
      state.caldav.add(task)
  for task in state.caldav.events:
    if not state.active.task_is_present(task):
      report(colour.red + 'Sanity: Task missing from active: ' + task.name + ' (group: ' + task.group() +')' + colour.end)
      # Task in caldav, not in active, add to active
      # Note the optional fields like starttext, hold, etc could be problematic in the sanity check
      state.active.add(task)

  if debug: report('CHANGE', debug=True)
  # changes
  change_names = []
  for change in changes:
    change_names.append(change.name)
  if len(changes) > 0:
    report(colour.blue + 'Identified possible changes in:' + colour.end + ' ' + (os.linesep+'  ').join([''] + change_names))

  for change in changes:
    task_a   = state.active.find_task(change)
    task_a_p = state_previous.active.find_task(change)
    task_c   = state.caldav.find_task(change)
    task_c_p = state_previous.caldav.find_task(change)
   
    # Improve the detection of changes to deal with the following better?
    if ((task_a is None) and (task_c is None) and (task_a_p is not None) and (task_c_p is not None)):
      report(colour.blue + 'Note for task' + colour.end + ' ' + change.name + ' ' + colour.blue + 'these changes are consistent with a simultaneous removal from both active and caldav, so ignoring (used to raise an error).' + colour.end)
      continue

    if any(x is None for x in [task_a, task_a_p, task_c, task_c_p]):
      detail = ''
      if task_a is None:   detail = detail + os.linesep + '  active          does not contain: ' + change.name
      if task_a_p is None: detail = detail + os.linesep + '  active previous does not contain: ' + change.name
      if task_c is None:   detail = detail + os.linesep + '  caldav          does not contain: ' + change.name
      if task_c_p is None: detail = detail + os.linesep + '  caldav previous does not contain: ' + change.name
      error('Task can not be found in one of the four collections: ' + change.name + detail)
      continue

    change_a = task_a != task_a_p
    change_c = task_c != task_c_p

    #print 'change_a', change_a
    #print 'change_c', change_c

    if change_c:
      state.aiyo.update(task_c, previous=task_c_p, caldavsource=True)

    if change_a:
      task_c.update(task_a, previous=task_a_p, caldav=True)

  #updated_next_actions = state.aiyo.find_next_actions()
  #print updated_next_actions
  state.aiyo.find_next_actions()
  #for task_a in state.active.events:
  #  task_a_p = state_previous.active.find_task(task_a)
  #  if task_a.next_action != task_a_p.next_action:
  #    task_a.set_updated(follow=False)
  #    print task_a.name, task_a.next_action

    

  # Clean up other changes to caldav required:
  additions, removals, updated = state.update_active()

  for task_a in updated.events:
    # TODO
    task_a_p = state_previous.active.find_task(task_a)
    task_c   = state.caldav.find_task(task_a)
    if (task_a_p is None or task_c is None):
      detail = ''
      if task_a_p is None: detail = detail + os.linesep + '  active previous does not contain: ' + task_a.name
      if task_c is None:   detail = detail + os.linesep + '  caldav          does not contain: ' + change.name
      error('Task can not be found in one of the four collections: ' + task_a.name + detail)
      continue
    report(colour.red + 'Task update discovered: ' + task_a.name + ' (group: ' + task_a.group() +')' + colour.end)
    task_c.update(task_a, previous=task_a_p, caldav=True)

  for task in additions.events:
    state.caldav.add(task)
  for task in removals.events:
    state.caldav.remove(task)

  return state


