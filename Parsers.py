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
import re
from Support import error, report

def urlbasename(string):
  return string.rstrip('/').split('/')[-1]

def calculate_delta(string):
  if string is None: return None
  num = re.findall('\d+', string)
  if len(num) > 0:
    n = float(num[0])
  else:
    n = 1
  if 'year' in string:
    d = timedelta(days = n * 365)
  elif 'month' in string:
    d = timedelta(days = n * 31)
  elif 'week' in string:
    d = timedelta(weeks = n)
  elif 'day' in string:
    d = timedelta(days = n)
  elif 'hour' in string:
    d = timedelta(hours = n)
  elif 'minute' in string:
    d = timedelta(minutes = n)
  elif 'random' in string:
    d = calculate_random()
  else:
    d = None
  return d

def calculate_random():
  from random import random
  day_min = timedelta(hours=6)
  day_max = timedelta(hours=23)
  day = timedelta(hours=24)
  buf = timedelta( minutes = (universe.now.hour * 60 + universe.now.minute) ) + timedelta(hours = 1)

  timerange = max( timedelta(seconds=0), (day_max - buf) ) + (day_max - day_min)
  #timerangeminutes = (timerange.total_seconds() % 3600) // 60
  timerangeminutes = timerange.total_seconds() // 60
  perturb = timedelta( minutes=int( timerangeminutes * random()  ))
  new = perturb + buf
  if new > day_max:
    new = new + day - day_max + day_min

  #shift = timedelta(seconds=((universe.now.hour * 60 + universe.now.minute) * 60 + universe.now.second)) + timedelta(microseconds=universe.now.microsecond) 
  shift = timedelta(minutes=(universe.now.hour * 60 + universe.now.minute))

  # .replace( second=0, microsecond=0)

  d = new - shift
  report(colour.magenta + 'Random repeat, in range of ' + colour.magentabright + str(timerange) + colour.magenta + ', chosen perturbation ' + colour.magentabright + str(perturb) + colour.magenta + ', to ' + colour.magentabright + str(d) + colour.end)
  return d

def timedelta_to_human(delta):
  def formatter(suffix, number):
    if number > 1:
      ess = 's'
    else:
      ess = ''
    return'%i%s%s' % (int(number), suffix, ess)
    
  minute = 60 
  hour   = 60 * minute
  day    = 24 * hour
  week   = 7 * day
  month  = 31 * day
  year   = 365 * day

  # Note this includes Feb, but also 4weeks
  monthtol = 3 * day
  yeartol = 2 * day
  tol = minute

  default_warning = hour

  seconds =  - (delta.seconds + delta.days * day )
  if seconds == 0:
    return ''
  elif seconds < 0:
    seconds = default_warning

  if (seconds // year > 0 and (seconds % year) < yeartol):
    d = formatter('year', seconds // year)
  elif (seconds // month > 0 and (seconds % month) < monthtol):
    d = formatter('month', seconds // month)
  elif (seconds // week > 0 and (seconds % week) < tol):
    d = formatter('week', seconds // week)
  elif (seconds // day > 0 and (seconds % day) < tol):
    d = formatter('day', seconds // day)
  elif (seconds // hour > 0 and (seconds % hour) < tol):
    d = formatter('hour', seconds // hour)
  elif (seconds // minute > 0 and (seconds % minute) < 5):
    d = formatter('minute', seconds // minute)
  else:
    d = None

  return d

def prioritystring(priority, shownone=False, spacer=False):
  if priority == 9:
    out_priority = '!'
  elif priority == 5:
    out_priority = '!!'
  elif priority == 1:
    out_priority = '!!!'
  else:
    if shownone:
      out_priority = '<none>'
    else:
      out_priority = ''
  if (spacer and len(out_priority) > 0):
    out_priority = ' ' + out_priority 
  return out_priority

#def is_same_time(time, string):
#  if time is None: return False
#  if string is None: return False
#  return (time.hour == int(string[:2]) and time.minute == int(string[2:]))

def is_same_time(a, b):
  if a is None:
    same = False
  elif b is None:
    same = False
  elif not (type(a) is datetime or type(a) is time):
    same = False
  elif not (type(b) is datetime or type(b) is time):
    same = False
  else:
    same = (a.hour == b.hour and a.minute == b.minute)
  return same

def is_relative_date(string):
  return (('year' in string) or ('month' in string) or ('week' in string) or ('day' in string) or ('hour' in string) or ('minute' in string))

def is_saturday(date):
  return date.weekday() == 5

def is_sunday(date):
  return date.weekday() == 6

def do_avoid_weekend(date, avoid_weekends=False):
  # if need to avoid weekends
  # if saturday, add two
  # if sunday, add one
  if avoid_weekends:
    if is_saturday(date):
      date = date + timedelta(days=2)
      report(colour.grey + '  Day is a Saturday, skipping until Monday' + colour.end)
    elif is_sunday(date):
      date = date + timedelta(days=1)
      report(colour.grey + '  Day is a Sunday, skipping until Monday' + colour.end)
  return date

def spacedemoji(string, plain=False):
  return string
  # if plain:
  #   return string
  # out = ''
  # try:
  #   for char in string.decode("utf-8"):
  #     en = char.encode("utf-8")
  #     out = out + en
  #     if len(en) > 1:
  #       out = out + ' '
  # except:
  #   return string
  # return out











