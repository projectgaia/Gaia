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
import pytz
from Support import update_now, set_default_times, globals_init
from Support import colourset
from Support import error, report, logging, clear_log, reporterror, tail
from Support import signal_init
from State import State, state_generate, aiyo_write, find_changes, diff   
from Support import repo_update
from CaldavClient import calendar_ctag

def usage(unknown = None):
  if unknown:
    print 'Unknown option ' + unknown
  print '''Usage for %(cmdname)s
 %(cmdname)s [options]
- Options ------------\ 
                      | Default: show active tasks
  priority, p         | Show active priority tasks
  inbox, i            | Show active inbox tasks
                      |---------------------------------------------
  daemon              | Daemonise
  reset, -r           | Reset caldav and saved state
                      |---------------------------------------------
  showall, -s         | Show databases
  showloglocation     | Show logfile location
  clear               | Clear log file
  backup              | Backup caldav calendars
  tail, -t            | Tail log
                      |---------------------------------------------
  -d                  | Dry run
  -l                  | Log to file, implies -p
  -v                  | Verbose
  -p                  | Plain output
  debug               | Show debugging messages
                      |   raise exceptions, instead of passing them to the log/stdout
  -h                  | Display help
  ctag                | Testing ctag 
                      \_____________________________________________''' % { 'cmdname': os.path.basename(sys.argv[0]) }
  sys.exit(0)

def main():
  class options:
    reset = False
    extras = []
    showall = False
    daemon = False
    once = False
    sleepsecs = 10
    plain = False
    clearlog = False
    log = False
    showloglocation = False
    taillog = False
    backupcaldav = False
    ctag = False
    priorityonly = False
    inboxonly = False
  args = sys.argv[1:]
  while (len(args) > 0):
    argument = args.pop(0).rstrip()
    if   (argument == '-h'):     usage()
    elif (argument == '-v'):     universe.verbose = True
    elif (argument == '-p'):     options.plain = True
    elif (argument == '-d'):     universe.dry = True
    elif (argument == '-1'):     options.once = True
    elif (argument == 'daemon'): options.daemon = True
    elif (argument == 'priority'): options.priorityonly = True
    elif (argument == 'p'): options.priorityonly = True
    elif (argument == 'inbox'): options.inboxonly = True
    elif (argument == 'i'): options.inboxonly = True
    elif (argument == 'debug'):  universe.debug = True #; options.sleepsecs = 1
    elif (argument == '-r'):     options.reset = True
    elif (argument == 'reset'):  options.reset = True
    elif (argument == '-s'):     options.showall = True
    elif (argument == 'showall'):   options.showall = True
    elif (argument == 'showloglocation'):   options.showloglocation = True; options.plain = True
    elif (argument == 'clear'):   options.clearlog = True
    elif (argument == 'backup'):  options.backupcaldav = True
    elif (argument == 'ctag'):   options.ctag = True
    elif (argument == 'tail'):   options.taillog = True
    elif (argument == '-t'):     options.taillog = True
    elif (argument == '-l'):     options.log = True; options.plain = True
    elif (argument.startswith('-')): usage(unknown = argument)
    else:
      options.extras = [ argument ] + options.extras

  set_default_times(due='1800', alarm='1000', duealt='0900', warning='0020')

  colourset(not options.plain)

  if options.log:
    universe.log = universe.logfile
    universe.bufferreturned = False
  else:
    universe.bufferreturned = True
    universe.log = None

  if options.backupcaldav:
    from CaldavClient import calendar_backup
    ok = True
    for calendar in universe.backupcalendars:
      universe.calendarcache.clear()
      lok = calendar_backup(principalurl=calendar)
      if not lok: ok = False
    if ok:
      sys.exit(0)
    else:
      sys.exit(1)

  if options.ctag:
    from CaldavClient import calendar_ctag
    calendar_ctag(debug=True)
    sys.exit(0)
    
  if options.clearlog:
    clear_log()
    sys.exit(0)

  if options.showloglocation:
    report(universe.logfile, forced=True)
    sys.exit(0)
  
  if options.taillog:
    tail(universe.logfile)
    sys.exit(0)

  if options.reset:
    from CaldavClient import calendars_clear
    state = State(generate=True)
    if not state.is_valid():
      report(colour.red + 'Problem generating state (initial)' + colour.end)
      sys.exit(1)
    report(colour.red + 'Reset caldav and saved state' + colour.end)
    state.caldav.remove_all()
    calendars_clear(state.aiyo.child_names() + universe.auxlists)
    for task in state.active.events:
      state.caldav.add(task)
    state = State(generate=True)
    if not state.is_valid():
      report(colour.red + 'Problem generating state (final)' + colour.end)
      sys.exit(1)
    state.save()
    sys.exit()

  if not (options.daemon or options.once or options.showall):
    universe.verbose = True
    show_notes = False
    state = State(generate=True, localonly=True)
    if not state.is_valid(localonly=True):
      report(colour.red + 'Problem generating state' + colour.end)
      sys.exit(1)
    # Show as a tree
    #if False:
    #  #state.aiyo.show_tree(notes=show_notes, activeonly=True)
    #  state.aiyo.show_tree(notes=show_notes, availableonly=True)

    state.active.show(show_notes=show_notes, wait_separate=True, priority_only=options.priorityonly, inbox_only=options.inboxonly)
    state.aiyo.show_error(show_notes=show_notes)

    
  # Need to contact caldav server
  if options.daemon or options.once or options.showall:
    from time import sleep
    from datetime import timedelta
    state_previous = State(load=True)
    #if not state_previous.is_valid():
    #  report(colour.red + 'Problem loading state' + colour.end)
    #  sys.exit(1)

    if options.showall:
      state = State(generate=True)
      if not state.is_valid():
        report(colour.red + 'Problem generating state' + colour.end)
        sys.exit(1)
      state.aiyo.show_tree()
      if state_previous.is_valid():
        report('-- STATE PREVIOUS')
        report(state_previous.to_string())
      report('-- STATE')
      report(state.to_string())
      sys.exit()

    if not state_previous.is_valid():
      report(colour.blue+'No previous state found, saving current state and continuing'+colour.end)
      state = State(generate=True)
      if not state.is_valid():
        report(colour.red + 'Problem generating state' + colour.end)
        sys.exit(1)
      state.save()
      state_previous = State(load=True)
      if not state_previous.is_valid():
        report(colour.red + 'Problem loading state' + colour.end)
        sys.exit(1)
      if not state_previous.is_valid():
        error('State generation and save error, exiting')
        sys.exit()

    #for t in state_previous.caldav.events:
    #  report('  ' + t.name + ' | ' + t.parents[0])

    #sys.exit()
    def task_props(state, state_previous, name, pre):
      ap = ''
      a  = ''
      cp = ''
      c  = ''
      try:
        a  = state.active.find_tasks_by_name(name=name)[0]
      except: pass
      try:
        ap = state_previous.active.find_tasks_by_name(name=name)[0]
      except: pass
      try:
        c  = state.caldav.find_tasks_by_name(name=name)[0]
      except: pass
      try:
        cp = state_previous.caldav.find_tasks_by_name(name=name)[0]
      except: pass
      print ''
      print pre, 'a ', a  #,  a.due.strftime('%y%m%d%H%M%S%z')
      print pre, 'ap', ap #, ap.due.strftime('%y%m%d%H%M%S%z')
      print pre, 'c ', c  #,  c.due.strftime('%y%m%d%H%M%S%z')
      print pre, 'cp', cp #, cp.due.strftime('%y%m%d%H%M%S%z')

    if options.daemon:
      signal_init()
      report(colour.blue + 'Awaking daemon' + colour.end + colour.grey + ', interlude %(interlude)ds' % {'interlude':universe.interlude}  + colour.end)

    from CaldavClient import calendar_ctag
    polllast = None
    consecutive = 0
    deduplicate_attempt = 0
    while True:
      universe.errors = u''
      universe.reportline = 0
      universe.reportcache = u''
      update_now()
      aiyo_changed = repo_update()
      caldav_changed = calendar_ctag()
      check = False

      #print aiyo_changed, caldav_changed, (polllast is None)
      if aiyo_changed: check = True
      if caldav_changed: check = True
      if deduplicate_attempt > 0: check = True
      if polllast is None:
        check = True
      elif universe.now >= polllast + timedelta(seconds=universe.routine):
        check = True
      
      if check:
        if (aiyo_changed and caldav_changed):
          report(colour.blue + 'Changed detected in aiyo and caldav' + colour.end)
        elif aiyo_changed:
          report(colour.blue + 'Changed detected in aiyo' + colour.end)
        elif caldav_changed:
          report(colour.blue + 'Changed detected in caldav' + colour.end)
        elif (deduplicate_attempt > 0):
          report(colour.blue + 'Duplicate to resolve' + colour.end)
        elif polllast is None:
          report(colour.blue + 'First instance, running as if there has been a change' + colour.end)
        elif (universe.now >= polllast + timedelta(seconds=universe.routine)):
          report(colour.blue + 'Routine check' + colour.end)

        state = State(generate=True, previous=state_previous)
        #task_props(state, state_previous, 'abcd', 1)

        if not state.is_valid():
          error('Problem generating state')
        else:
          #state.sort_groups()
          deduplicate_attempt += 1
          # Try twice, if persists on third attempt, act and deduplicate
          deduplicate_stat = state.deduplicate(forced=(deduplicate_attempt >= 3))
          if not deduplicate_stat:
            report(colour.red + ('Duplicates found, attempt %i skipping in this run' % deduplicate_attempt) + colour.end)
          else:
            deduplicate_attempt = 0
            state = diff(state, state_previous)
            aiyo_write(state)
            state.save()
            # This second update can mean changes from other clients are missed
            # Downside to not doing this update here, is a check is made when gaia itelf changes the server content, as the ctag is not updated.
            #calendar_ctag()
            #task_props(state, state_previous, 'abcd', 2)
            if not options.daemon:
              break
            state_previous = state

      poll = False
      if (polllast is None or universe.debug):
        poll = True
      elif universe.now >= polllast + timedelta(seconds=universe.interlude):
        poll = True
      # Show poll mark if there has been some action!
      if universe.reportline > 0:
        poll = True
        consecutive += 1
        if consecutive >= 20:
          if (consecutive == 20 or (consecutive % 360) == 0):
            error('Consecutive operation, '+str(consecutive)+' in total so far')
      else:
        consecutive = 0
      reporterror()
      if poll:
        if (universe.debug and polllast is not None):
          report(colour.cyan + '[%.0d]' % (universe.now-polllast).total_seconds() + colour.end, noreturn=True)
        report(colour.blue + '.' + colour.end, noreturn=True)
        polllast = universe.now
      if universe.killed: break
      sleep(options.sleepsecs)
      if universe.killed: break
    if universe.killed:
      report(colour.red + 'Completed loop and gracefully exited' + colour.end)

def prime():
  #main_with_error_capture
  globals_init()
  update_now()
  colourset(True)
  try:  
    main()
  except Exception, e:
    if ('debug' in sys.argv[1:] or universe.debug):
      raise
    coreerror = '**** CORE ERROR, exception: ' + str(e)
    coreerror = coreerror + '\n' + str(e.__doc__)
    coreerror = coreerror + '\n' + str(sys.exc_info())
    #ex_type, ex, tb = sys.exc_info()
    #sys.exc_info()[2], 'line...',traceback.tb_lineno(sys.exc_info()[2])
    #traceback.print_tb(tb)
    #  + '  on line {}'.format(sys.exc_info()[0].tb_lineno)
    print coreerror.encode('utf-8')
    try:
      f = open(universe.logfile, 'a')
      f.write((os.linesep + coreerror).encode('utf-8'))
      f.close()
    except:
      pass
    error(coreerror)
    reporterror()
    sys.exit(1)

if __name__ == '__main__':
  prime()


