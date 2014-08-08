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
import re
from datetime import datetime, timedelta, time
import pytz
import subprocess
import signal
for path in ['~/bin/', '~/bin/common/']: sys.path.append(os.path.expanduser(path))
import prowlpy

try:
  from subprocess import DEVNULL # py3k
except ImportError:
  import os
  DEVNULL = open(os.devnull, 'wb')

def set_default_times(due='1800', alarm='1000', duealt='0900', warning='0020'):
  def generator(string):
    t = time(hour=int(string[:2]), minute=int(string[2:]), tzinfo=universe.timezone)
    d = timedelta(minutes=(t.hour * 60 + t.minute))
    return t, d
  def diffgenerator(string):
    hour = int(string[:2])
    minute = int(string[2:])
    d = timedelta(minutes=(hour * 60 + minute))
    return d

  class defaulttime:
    due = None
    duealt = None
    alarm = None
    duedelta = None
    duealtdelta = None
    alarmdelta = None
    alldaydiff = None
    diff = None

  defaulttime.due, defaulttime.duedelta = generator(due)
  defaulttime.alarm, defaulttime.alarmdelta = generator(alarm)

  if duealt is not None:
    defaulttime.duealt, defaulttime.duealtdelta = generator(duealt) 

  defaulttime.alldaydiff = defaulttime.alarmdelta - defaulttime.duedelta
  defaulttime.diff = - diffgenerator(warning)
  universe.defaulttime = defaulttime

def update_now():
  universe.now = universe.timezone.localize(datetime.now())
  #now = now.astimezone(timezone)

class pretty:
  red = '\033[0;31m'
  redbright = '\033[1;31m'
  cyan = '\033[0;36m'
  cyanbright = '\033[1;36m'
  blue = '\033[0;34m'
  bluebright = '\033[1;34m'
  yellow = '\033[0;33m'
  yellowbright = '\033[1;33m'
  green = '\033[0;32m'
  greenbright = '\033[1;32m'
  magenta = '\033[0;35m'
  magentabright = '\033[1;35m'
  grey = '\033[1;30m'
  end = '\033[0m'

class plain:
  red = ''
  redbright = ''
  cyan = ''
  cyanbright = ''
  blue = ''
  bluebright = ''
  yellow = ''
  yellowbright = ''
  green = ''
  greenbright = ''
  magenta = ''
  magentabright = ''
  grey = ''
  end = ''

def colourset(is_pretty):
  if is_pretty:
    b = pretty
  else:
    b = plain
  colour.red = b.red
  colour.redbright = b.redbright
  colour.cyan = b.cyan
  colour.cyanbright = b.cyanbright
  colour.blue = b.blue
  colour.bluebright = b.bluebright
  colour.yellow = b.yellow
  colour.yellowbright = b.yellowbright
  colour.green = b.green
  colour.greenbright = b.greenbright
  colour.magenta = b.magenta
  colour.magentabright = b.magentabright
  colour.grey = b.grey
  colour.end = b.end
  return None

def generate_mono(is_plain):
  if is_plain:
    return plain
  else:
    return colour

def signal_init():
  signal.signal(signal.SIGINT, graceful)

def graceful(signal, frame):
  universe.killed = True
  report(colour.red + 'Killed! Waiting for process to reach sleep period...' + colour.end)
  return

def clear_log():
  f = open(universe.logfile, 'w')
  f.write(''.encode('utf-8'))
  f.close()
  print colour.blue + 'Log cleared: ' + universe.logfile + colour.end

def logging():
  return universe.log is not None

def report(string, forced=False, noreturn=False, debug=False, routine=False):
  # routine messages do not get added to consecutive reports, cauing error on multiple reports
  if debug and not universe.debug: return
  if (not debug and not routine):
    # Only change report lines for non-debug messages
    universe.reportline += 1
    # Don't include debug messages in repo commits
    universe.reportcache = universe.reportcache + string + os.linesep
  if (universe.verbose or forced):
    if logging():
      if noreturn:
        universe.bufferreturned = False
      else:
        string = string + os.linesep
        if not universe.bufferreturned:
          string = os.linesep + string
          universe.bufferreturned = True
      f = open(universe.log, 'ab')
      # Can cause trouble!
      f.write(string.encode('utf-8'))
      f.close()
    else:
      if noreturn:
        universe.bufferreturned = False
        sys.stdout.write(string.encode('utf-8'))
        sys.stdout.flush()
      else: 
        if not universe.bufferreturned:
          print ''.encode('utf-8')
          universe.bufferreturned = True
        print string.encode('utf-8')

def error(string, fatal=False):
  stringexit = ''
  if fatal:
    stringexit = ' [FATAL ERROR, exiting]'
  report(colour.redbright + 'ERROR:' + colour.end + ' ' + colour.red + string + colour.end + colour.redbright + stringexit + colour.end, forced=True)
  if len(universe.errors) > 0:
    universe.errors = universe.errors + os.linesep
  universe.errors = universe.errors + string + stringexit
  if fatal:
    sys.exit(1)

def prowl(event, description):
  try:
    p = prowlpy.Prowl(None, check='gaia')
    p.post('Todocal', event.encode('utf-8'), description.encode('utf-8'), 0, None, None)
    universe.prowllast = universe.now
  except Exception, e:
    report('Error with prowl, exception: ' + str(e))
    pass

def reporterror(force=False):
  if len(universe.errors) == 0: return
  if not force:
    if universe.prowllast is not None:
      if universe.prowllast < universe.now - timedelta(minutes = 30):
        return
  prowl('ERROR', universe.errors)
  universe.prowllast = universe.now
  report(colour.blue + 'Reported errors' + colour.end, forced=True)
  
def execute(cmd, stat=False, background=False, env=None, shell=False, showerror=False):
  if showerror:
    stderror = subprocess.PIPE
  else:
    stderror = DEVNULL
  s = subprocess.Popen(cmd, stderr=stderror, stdout=subprocess.PIPE, env=env, shell=shell)
  if background:
    return ''
  s.wait()
  if stat:
    return [s.returncode, s.communicate()[0]]
  else:
    return s.communicate()[0]

def repo_add(filename, prefix=''):
  cmd = [ 'svn', 'add', filename.encode('utf-8') ]
  out = execute(cmd)
  report(prefix+colour.blue + 'Repo add file:' + colour.end + ' ' + colour.bluebright + filename + colour.end + ' ' + colour.grey + re.sub('  +',' ',' '.join(out.splitlines())) + colour.end)

def repo_remove(filename):
  cmd = [ 'svn', 'remove', '--force', filename.encode('utf-8') ]
  out = execute(cmd)
  report(colour.blue + 'Repo remove file:' + colour.end + ' ' + colour.bluebright + filename + colour.end + ' ' + colour.grey + re.sub('  +',' ',' '.join(out.splitlines())) + colour.end)

def repo_update(commit=False, root=None):
  changed = False
  make_report = False
  if root is None:
    root = universe.dataroot
  action = 'Update'
  cmd = [ 'svn', 'update', '--accept', 'theirs-conflict', root ]
  out = execute(cmd)
  if 'Updated to revision' in out:
    changed = True
  #if 'At revision ' not in out:
  #  make_report = True
  # Add a check on svn st?  Sometimes if a change is identified, but actually file is the same - could check this here, or earlier with a diff on file contents and proposed file contents?
  #   Would prevent whitespace after | below
  if commit:
    action = action + ' and archive'
    message = 'Gaia update:' + os.linesep + os.linesep.join([ '  ' + line if len(line) > 0 else line for line in universe.reportcache.splitlines() ])
    cmd = [ 'svn', 'commit', '--non-interactive', '-m', message.encode('utf-8'), root ]
    outcommit = execute(cmd, showerror=True).decode('utf-8')
    if len(outcommit.strip()) == 0:
      outcommit = '<NO COMMIT OCCURRED>'
    out = out + ' | ' + outcommit
    out = re.sub(' +',' ',out)
    out = re.sub(' *\t *',' ',out)
    out = re.sub(' \.','.',out)
    make_report = True
  if make_report: 
    report(colour.blue + action + ' of files:' + colour.end + ' ' + colour.grey + re.sub('  +',' ',' '.join(out.splitlines())) + colour.end)
  return changed

def globals_init():
  debug = False
  # Config file ('~/.gaia') format:
  # [general]
  # calendars = https://caldav.server.address/and/path
  # aiyo = ~/path/to/aiyo/tasks/folder/
  # log = /var/log/gaia.log
  # timezone = Europe/London
  # auxlists = wait, grocery, checklist
  # skipweekendlists = work, research
  # 
  # [backup]
  # location = ~/path/to/calendar/backup/folder/,~/path/to/second/calendar/folder/

  import ConfigParser
  def read_config():
    configfiles = [ '~/.gaia', '~/.common/.gaia' ]
    configfile = None
    for configfileraw in configfiles:
      configfile = os.path.expanduser(configfileraw)
      if os.path.exists(configfile): 
        break
      configfile = None
    if configfile is None:
      error('Configuration file not found, from possibles: ' + ', '.join(configfiles), fatal=True)
      sys.exit()
    Config = ConfigParser.ConfigParser()
    if debug:
      print 'Read config file:', configfile
    Config.read(configfile)
    return Config

  universe.reportcache = u''
  universe.verbose = False
  universe.debug = False
  universe.errors = ''
  universe.dry = False
  universe.bufferreturned = True
  universe.killed = False
  universe.calendarcache = dict()
  universe.calendarctag = dict()
  universe.calendaraddresstoname = dict()
  universe.principalurl = ''
  universe.routine = 60 * 60
  # Might not be able to write to?  Do a test write?
  universe.reportline = 0
  universe.next_char = '➘ '.decode('utf-8')
  #universe.next_char = '⤥ '.decode('utf-8')
  #universe.next_char = '-> '

  config = read_config()
  try:
    universe.principalurl = config.get('general', 'calendars').strip()
  except:
    error('Problem reading principal calendar URL')
  try:
    universe.dataroot = os.path.expanduser(config.get('general', 'aiyo').strip()).rstrip('/')+'/'
  except:
    error('Problem reading aiyo data root folder')
  try:
    universe.logfile = config.get('general', 'log').strip()
  except:
    error('Problem reading log file location')
  try:
    universe.next_char = config.get('general', 'next_char').strip().decode('utf-8')
  except:
    # Not compulsory
    pass
    #error('Problem reading next character')
  try:
    universe.timezone = pytz.timezone(config.get('general', 'timezone').strip())
  except:
    error('Problem reading timezone')
  try:
    universe.auxlists = []
    auxlist = config.get('general', 'auxlists').strip().split(',')
    if len(auxlist) == 0:
      error('Problem reading aux lists')
    for calendar in auxlist:
      if len(calendar) == 0: continue
      universe.auxlists.append(calendar.strip())
  except:
    error('Problem reading aux lists')
  try:
    universe.category_order = []
    category_order = config.get('general', 'category_order').strip().split(',')
    if len(category_order) == 0:
      error('Problem reading category_order')
    for calendar in category_order:
      if len(calendar) == 0: continue
      universe.category_order.append(calendar.strip())
  except:
    pass
    #error('Problem reading category_order')
  try:
    universe.skipweekendlists = []
    skipweekendlist = config.get('general', 'skipweekendlists').strip().split(',')
    if len(skipweekendlist) == 0:
      error('Problem reading skipweekend lists')
    for calendar in skipweekendlist:
      if len(calendar) == 0: continue
      universe.skipweekendlists.append(calendar.strip())
  except:
    error('Problem reading aux lists')
  try:
    universe.backuproot = os.path.expanduser(config.get('backup', 'location').strip()).rstrip('/')+'/'
  except:
    error('Problem reading calendar backup location')
  try:
    universe.interlude = int(config.get('general', 'interlude').strip())
  except:
    error('Problem reading interlude time')
  try:
    universe.routine = int(config.get('general', 'routine').strip())
  except:
    pass

  try:
    universe.backupcalendars = [ universe.principalurl ]
    backupcalendars = config.get('backup', 'calendars').strip().split(',')
    if len(backupcalendars) == 0:
      error('Problem reading backup calendar URLs')
    for calendar in backupcalendars:
      if len(calendar) == 0: continue
      universe.backupcalendars.append(calendar.strip())
  except:
    error('Problem reading backup calendar URLs')
  
  universe.statefile = universe.dataroot + '.state'
  
  if debug:
    print 'principalurl    ', universe.principalurl
    print 'dataroot        ', universe.dataroot
    print 'logfile         ', universe.logfile
    print 'timezone        ', universe.timezone
    print 'auxlists        ', universe.auxlists
    print 'statefile       ', universe.statefile
    print 'backupcalendars ', universe.backupcalendars

def tail(filename):
  signal_init()
  import time
  def follow(thefile):
    thefile.seek(0,2)      # Go to the end of the file
    while True:
      line = thefile.readline().decode('utf-8')
      if not line:
        time.sleep(0.1)    # Sleep briefly
        if universe.killed: break
        continue
      yield line

  if not os.path.exists(filename):
    error('Log file not found', fatal=True)
  try:
    logfile = open(filename)
    #line = colour.grey + logfile.read().decode('utf-8') + colour.end
    # Limit to last 50 lines:
    line = colour.grey + '\n'.join(logfile.read().splitlines()[-50:]).decode('utf-8') + colour.end + '\n'
    sys.stdout.write(line.encode('utf-8'))
    sys.stdout.flush()
  except:
    error('Problem reading log', fatal=True)
  loglines = follow(logfile)
  for line in loglines:
    sys.stdout.write(line.encode('utf-8'))
    sys.stdout.flush()
  print ''



